import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sentinel.tasks import definitions

TASK_DIR = definitions.CORE_TASKS_DIR / "analyze-security"


@pytest.fixture
def source_server():
    requests = []
    table = (
        "<html><nav>Navigation noise</nav><main><h1>Fund holdings</h1><table>"
        "<tr><th>Company</th><th>Portfolio weight</th></tr>"
        "<tr><td>Alpha Bank</td><td>25 percent of net assets</td></tr>"
        "<tr><td>National Bank</td><td>30 percent of net assets</td></tr>"
        "</table><script>Hidden script noise</script></main></html>"
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(("summary", payload["url"]))
            usable = "/good/" in payload["url"]
            self.respond(
                json.dumps(
                    {
                        "ok": usable,
                        "url": payload["url"],
                        "title": payload["title"],
                        "summary": "A supported structural finding." if usable else "",
                        "content": "Unsummarized financial evidence. " * 1000 if "/cached/" in payload["url"] else "",
                        "error": None if usable else "insufficient paragraphs",
                    }
                ),
                "application/json",
            )

        def do_GET(self):  # noqa: N802
            requests.append(("raw", self.path))
            if self.path.startswith("/denied/"):
                self.respond("Forbidden", "text/plain", status=403)
            elif self.path.startswith("/challenge/"):
                self.respond("<main>Verify you are human. " + "Please wait. " * 20 + "</main>", "text/html")
            else:
                self.respond(table, "text/html")

        def respond(self, text, content_type, status=200):
            body = text.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _search_text(urls):
    return "\n\n".join(f"Title: Source {i}\nDescription: Evidence\nURL: {url}" for i, url in enumerate(urls))


def _fetch(tmp_path, base, urls, allow_raw):
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(TASK_DIR / "fetch-query-sources.py")],
        env=os.environ
        | {
            "WORK_ROOT": str(tmp_path),
            "QUERY": "holdings",
            "SEARCH_TEXT": _search_text(urls),
            "ALLOW_RAW_CONTENT": str(allow_raw).lower(),
            "SENTINEL_URL_SUMMARIZER_BASE_URL": base,
        },
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
    return json.loads(result.stdout)


def test_raw_financial_table_is_used_only_after_recovery(tmp_path, source_server):
    base, requests = source_server
    urls = [base + "/table/1"]
    first = _fetch(tmp_path, base, urls, False)
    assert first["sourceCount"] == 0
    assert all(kind == "summary" for kind, _ in requests)

    recovered = _fetch(tmp_path, base, urls, True)
    assert recovered["rawSourceCount"] == recovered["sourceCount"] == 1
    text = (tmp_path / "query-source-summaries" / f"{recovered['queryHash']}.md").read_text()
    assert "Unsummarized source content" in text
    assert "Alpha Bank | 25 percent" in text
    assert urls[0] in text
    assert "Navigation noise" not in text
    assert "Hidden script noise" not in text
    assert recovered["failures"][0]["error"] == "insufficient paragraphs"


def test_summaries_are_preferred_and_cached_content_is_bounded(tmp_path, source_server):
    base, requests = source_server
    output = _fetch(tmp_path, base, [base + "/cached/1", base + "/good/1"], True)
    assert output["sourceCount"] == 2
    assert output["rawSourceCount"] == 1
    text = (tmp_path / "query-source-summaries" / f"{output['queryHash']}.md").read_text()
    assert text.index("A supported structural finding") < text.index("Unsummarized financial evidence")
    assert "truncated at 20,000 characters" in text
    assert all(kind == "summary" for kind, _ in requests)


@pytest.mark.parametrize("path", ["denied", "challenge"])
def test_inaccessible_content_remains_a_recorded_failure(tmp_path, source_server, path):
    base, _ = source_server
    output = _fetch(tmp_path, base, [base + f"/{path}/1"], True)
    assert output["sourceCount"] == 0
    assert [failure["stage"] for failure in output["failures"]] == ["summary", "raw"]


@pytest.mark.parametrize("mode", ["summaries", "raw", "repeat", "search-error", "unusable"])
def test_task_recovers_sources_for_profile_security_and_context(tmp_path, source_server, mode):
    base, requests = source_server
    item = {
        "name": "Test Security",
        "symbol": "TEST",
        "workRoot": str(tmp_path),
        "contextRoot": str(tmp_path / "context"),
    }
    # Run the real task.js and fetch helpers; replace only unrelated LLM/report steps.
    harness = r"""
const {readFileSync} = require('node:fs');
const {execFileSync} = require('node:child_process');
const {join} = require('node:path');
const item = JSON.parse(process.env.TEST_ITEM);
const mode = process.env.TEST_MODE;
const base = process.env.SENTINEL_URL_SUMMARIZER_BASE_URL;
const calls = [], logs = [], evidence = [];
const run = async (file, options = {}) => {
  if (file.startsWith('fetch-') || file.startsWith('load-query') || file.startsWith('load-profile-summaries')) {
    return execFileSync(process.env.TEST_PYTHON, [join(process.env.TEST_TASK_DIR, file)], {
      env: {...process.env, ...options.env}, encoding: 'utf8',
    });
  }
  if (file === 'resolve-security.py') return JSON.stringify([item]);
  if (file === 'save-queries.py') return JSON.stringify(['security query']);
  if (file === 'validate-context-queries.py') return JSON.stringify(['context query']);
  return 'Profile or saved findings';
};
const tool = async (_name, args) => {
  calls.push(args);
  if (mode === 'search-error' && args.pageno === 2) throw new Error('search unavailable');
  let urls;
  if (mode === 'summaries' && args.pageno === 2) urls = Array.from({length: 5}, (_, i) => `${base}/good/${i}`);
  else urls = [`${base}/${mode === 'unusable' ? 'denied' : 'table'}/${mode === 'repeat' ? 1 : args.pageno}`];
  return urls.map((url, i) => `Title: Source ${i}\nDescription: Evidence\nURL: ${url}`).join('\n\n');
};
const prompt = async (file, options) => {
  if (options.context.querySummaries) evidence.push(options.context.querySummaries);
  if (options.context.profileSummaries) evidence.push(options.context.profileSummaries);
  return 'Supported findings';
};
const console = {log: value => logs.push(value), warn: value => logs.push(value)};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
try {
  const source = readFileSync(join(process.env.TEST_TASK_DIR, 'task.js'), 'utf8');
  const fn = new AsyncFunction('run', 'tool', 'prompt', 'console', 'process', source);
  await fn(run, tool, prompt, console, process);
  process.stdout.write(JSON.stringify({calls, logs, evidence}));
} catch (error) {
  process.stdout.write(JSON.stringify({calls, logs, error: error.message}));
}
"""
    result = subprocess.run(  # noqa: S603
        [shutil.which("node") or "node", "--input-type=commonjs", "--eval", "(async()=>{" + harness + "})()"],
        env=os.environ
        | {
            "TEST_ITEM": json.dumps(item),
            "TEST_MODE": mode,
            "TEST_PYTHON": sys.executable,
            "TEST_TASK_DIR": str(TASK_DIR),
            "SENTINEL_URL_SUMMARIZER_BASE_URL": base,
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    output = json.loads(result.stdout)
    pages = 3 if mode in {"raw", "unusable"} else 2
    if mode == "unusable":
        assert "No usable source summaries or raw content" in output["error"]
        assert len(output["calls"]) == pages
        return
    assert "error" not in output, output
    assert len(output["calls"]) == 3 * pages
    assert {call.get("time_range") for call in output["calls"]} == {None, "year", "month"}
    assert output["calls"][0]["query"] == "strategy of Test Security for the next 10 years"
    assert len(output["evidence"]) == 3
    if mode == "summaries":
        assert all("Unsummarized source content" not in text for text in output["evidence"])
        assert all(kind == "summary" for kind, _ in requests)
    else:
        assert all("Unsummarized source content" in text for text in output["evidence"])
        assert any("summary failed" in text for text in output["logs"])
