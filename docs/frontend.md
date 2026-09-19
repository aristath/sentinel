# Frontend and Teract

Sentinel's browser interface is a small Lit application made from custom
elements. Teract supplies dependency-free TUI primitives and the global theme;
Sentinel owns application behavior, data loading, and domain-specific elements.

## Runtime stack

| Layer | Responsibility |
|---|---|
| Browser platform | Custom elements, fetch, events, and accessibility semantics |
| Lit | Reactive rendering for Sentinel application elements |
| Teract | Native custom elements, Unicode TUI controls, charts, layout, and theme |
| CodeMirror 6 | Task prompt/code editing inside the Research modal |
| Vite | Development server and production bundling |

Teract itself must remain native and dependency-free. Lit and CodeMirror are
Sentinel dependencies; they must not be moved into Teract.

The package reference is local:

```json
{
  "teract": "file:../../teract"
}
```

The expected checkout layout is therefore:

```text
~/sentinel/
~/teract/
```

## Element tree

`web/src/main.js` imports Teract, its global stylesheet, and the Sentinel
elements. `<sentinel-app>` builds the page:

```text
sentinel-app
├── sentinel-header
├── main
│   ├── sentinel-portfolio-status
│   ├── sentinel-planner-status
│   ├── sentinel-portfolio-value
│   ├── sentinel-portfolio-pnl
│   └── sentinel-securities
└── sentinel-status-bar
```

The header owns command/navigation modals. Research contains the Status, Units,
History, Chat, and Tasks tabs; Tasks is not an independent top-level command.
Chat keeps its current browser-session transcript when the modal closes and
sends the transcript with each follow-up request.

## Development

Start the API from the repository root:

```bash
source .venv/bin/activate
python main.py
```

Then start Vite from `web/`:

```bash
npm install
npm run dev
```

The permanent defaults are:

- Sentinel API: `http://localhost:8000`
- Vite: `http://localhost:5173`
- Vite `/api` proxy target: `http://localhost:8000`

Higher workstation ports may be selected on the command line for simultaneous
development sessions. They are local runtime choices and must not replace the
defaults in `web/vite.config.js` or production configuration.

For example:

```bash
python main.py --port 43127
cd web
npm run dev -- --port 43128
```

The tracked Vite proxy still targets port 8000. A parallel session that also
needs a different API port must use a temporary/untracked Vite configuration
for that proxy target. Do not commit workstation-specific ports.

## Data loading and mutations

`web/src/live-resource.js` is the standard polling controller. It:

1. loads immediately when its host connects;
2. aborts an older request before a refresh;
3. requests a host render for loading, data, and error changes;
4. polls every 30 seconds by default; and
5. stops its timer and request when disconnected.

Use the helpers in `web/src/api.js` for JSON requests. Mutation errors expose
the API's `detail` message when available. Preserve existing behavioral
semantics during UI work: a visual migration must not add confirmation steps or
change when an operation runs unless that behavior change is explicitly
requested.

## Rendering rules

Sentinel elements use light DOM:

```js
createRenderRoot() {
  return this;
}
```

This lets the Teract theme inherit through the application and keeps the result
close to real terminal markup. It also means DOM ownership must remain clear:

- Render reactive content through Lit templates.
- Do not assign `innerHTML` or `textContent` to an element containing Lit parts.
- Do not recreate a Teract control merely to update its value.
- Preserve authored children such as `<option>` nodes.

Violating these rules can eject Lit marker nodes and produce
`ChildPart has no parentNode` errors.

## Visual rules

- Component-specific CSS is self-contained in the element as inline `style`
  attributes.
- Only global page/theme behavior belongs in Teract's global CSS.
- Use real Unicode borders, separators, sparklines, and Braille chart cells.
- Status uses foreground color. Do not turn status text into colored badges.
- Keep table content left-aligned so `|` separators remain visually stable.
- Long content wraps. Components must not cause horizontal page growth.
- Expanded security details may be boxed; the expanded row heading, not the
  detail box, receives reverse colors.
- Light mode uses a white page and dark text; dark mode uses a black page and
  light text.

Teract additions should be generic primitives that are useful outside Sentinel.
Domain-specific composition stays in `web/src/`.

## Production build

From `web/`:

```bash
npm ci
npm run build
```

Vite writes `web/dist/`. When that directory exists, FastAPI mounts its assets
and serves `index.html` for non-API routes. The build output is tracked in this
repository, so a UI release must include the corresponding `web/dist` changes.

See [Testing](testing.md#frontend) for the required verification and
[Deployment](deployment.md) for production release rules.
