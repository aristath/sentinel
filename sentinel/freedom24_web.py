"""
Freedom24 web-session client.

The public TraderNet API doesn't expose the PRAAMS portfolio-analysis data
shown on https://freedom24.com/portfolios/structure/ (Portfolio Ratio, the
Risk/Return radar, sector/region/currency breakdowns, replace-position
recommendations, etc.). That page is server-rendered HTML containing an
inline `const props = {...}` blob and requires a web-session SID cookie.

This client logs in with login/password against `freedom24.com/api/`
(`cmd: "authByLogin"`), keeps the cookie jar in an `httpx.AsyncClient`,
fetches the structure page, and returns the parsed `portfolioAnalysis` dict.
The session is cached in memory and re-established on demand if the SID
expires.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from sentinel.settings import Settings
from sentinel.utils.decorators import singleton

logger = logging.getLogger(__name__)

LOGIN_URL = "https://freedom24.com/api/"
STRUCTURE_URL = "https://freedom24.com/portfolios/structure/"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

CACHE_TTL_S = 300


def _extract_props(html: str) -> dict | None:
    """Pull the `const props = {...};` JSON blob out of the structure page."""
    m = re.search(r"const props\s*=\s*\{", html)
    if not m:
        return None
    s = html[m.end() - 1 :]
    depth = 0
    in_str = False
    esc = False
    end = 0
    for i, c in enumerate(s):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == 0:
        return None
    try:
        return json.loads(s[:end])
    except json.JSONDecodeError:
        return None


@singleton
class Freedom24WebClient:
    """Async client that maintains a logged-in session against freedom24.com."""

    _settings: "Settings"
    _client: httpx.AsyncClient | None
    _lock: asyncio.Lock
    _cached: dict | None
    _cached_at: float

    def __init__(self) -> None:
        self._settings = Settings()
        self._client = None
        self._lock = asyncio.Lock()
        self._cached = None
        self._cached_at = 0.0

    async def _login(self, client: httpx.AsyncClient, login: str, password: str) -> bool:
        payload = {
            "q": json.dumps(
                {
                    "cmd": "authByLogin",
                    "params": {
                        "login": login,
                        "password": password,
                        "rememberMe": 1,
                    },
                }
            )
        }
        try:
            r = await client.post(LOGIN_URL, data=payload)
            r.raise_for_status()
            body = r.json()
        except httpx.HTTPError as e:
            logger.warning("Freedom24 login HTTP error: %s", e)
            return False
        except json.JSONDecodeError:
            logger.warning("Freedom24 login: non-JSON response")
            return False
        if not (body.get("success") and body.get("SID")):
            # Log only the safe fields. SID/auth_code_id stay out of logs.
            safe = {k: v for k, v in body.items() if k not in ("SID", "auth_code_id")}
            logger.warning("Freedom24 login refused: %s", safe)
            return False
        logger.info("Freedom24 login OK (userId=%s)", body.get("userId"))
        return True

    async def _drop_client(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as e:  # noqa: BLE001 - best-effort cleanup
                logger.debug("Error closing freedom24 http client: %s", e)
            self._client = None

    async def _ensure_client(self) -> bool:
        """Make sure we have a logged-in httpx client. Returns False if creds missing."""
        if self._client is not None:
            return True
        login = await self._settings.get("freedom24_login")
        password = await self._settings.get("freedom24_password")
        if not login or not password:
            return False
        client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if not await self._login(client, login, password):
            await client.aclose()
            return False
        self._client = client
        return True

    async def get_portfolio_structure(self, force_refresh: bool = False) -> dict | None:
        """Return the parsed `portfolioAnalysis` dict, or None if unavailable."""
        now = time.time()
        if not force_refresh and self._cached is not None and (now - self._cached_at) < CACHE_TTL_S:
            return self._cached

        async with self._lock:
            # Recheck cache after acquiring the lock — another coroutine may have
            # populated it while we were waiting.
            now = time.time()
            if not force_refresh and self._cached is not None and (now - self._cached_at) < CACHE_TTL_S:
                return self._cached

            # Try once with the existing session, then once after a fresh login.
            for attempt in (0, 1):
                if not await self._ensure_client():
                    return None
                client = self._client
                if client is None:  # pragma: no cover - _ensure_client guarantees this
                    return None
                try:
                    r = await client.get(STRUCTURE_URL)
                    r.raise_for_status()
                    html = r.text
                except httpx.HTTPError as e:
                    logger.warning(
                        "Freedom24 structure fetch failed (attempt %d): %s",
                        attempt + 1,
                        e,
                    )
                    await self._drop_client()
                    continue

                props = _extract_props(html)
                if props is None:
                    # Common cause: SID expired and we got the login page back.
                    # Drop and retry once with a fresh login.
                    logger.info(
                        "No props blob in structure page (attempt %d) — re-authing",
                        attempt + 1,
                    )
                    await self._drop_client()
                    continue

                self._cached = props
                self._cached_at = time.time()
                return props

        return None

    async def close(self) -> None:
        """Close any open HTTP client (idempotent)."""
        async with self._lock:
            await self._drop_client()
