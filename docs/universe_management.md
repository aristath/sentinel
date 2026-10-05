# Universe management

`sentinel/universe.py` reconciles Sentinel's active securities with the user's
default Freedom24 stock list (Favorites). Reconciliation is run by the
`sync:metadata` fixed job; there is no dedicated universe/import HTTP endpoint.

## Provenance

`securities.universe_source` records why a security is active:

| Value | Meaning |
|---|---|
| `freedom24_default` | Present in the Freedom24 default stock list |
| `broker_position` | Retained because the broker reports a non-zero position |

`universe_last_seen_at` records the latest successful Favorites observation.

## Reconciliation

`reconcile_universe_from_freedom24_default_list()`:

1. fetches the broker's user stock lists;
2. selects the list identified by `defaultId`;
3. extracts its non-empty ticker strings;
4. adds or reactivates missing favorites;
5. restores buying when a position-retained security returns to Favorites; and
6. applies the removal rules below to active symbols no longer present.

The run is skipped without mutation if the default list is unavailable or
empty. It is also skipped when proposed additions plus removals exceed 50
percent of the current active universe. That guard prevents a malformed or
partial upstream response from disabling most securities.

## Import behavior

`import_security_from_broker()` obtains name, currency, market ID, and minimum
lot when available, then activates buying and selling. New geography and
industry values are deliberately left for metadata sync, which uses the
broker's country-of-risk and sector attributes. Existing analysis history and
metadata survive reactivation.

Imports normally request 20 years of historical prices. A metadata or history
failure is logged and does not undo the security row; a later sync retries it.

Manual security creation is available through `POST /api/securities`, described
in [Securities API](api/securities.md). It adds the symbol to Freedom24 Favorites
before importing it locally; later Favorites reconciliation therefore retains it.
The MCP `security_add` tool uses the same operation.

`GET /api/securities/search` and MCP `securities_search` discover instruments in
Tradernet's catalog before adding them. Search results distinguish active,
inactive, and untracked local symbols and include exact broker symbols for
subsequent operations. `GET /api/securities/{symbol}/broker-info` and MCP
`security_broker_info_get` inspect broker metadata without importing the symbol.
See [MCP](mcp.md#securities-and-account-history) for the complete workflow.

## Removal rules

When a symbol disappears from Favorites:

- With a non-zero position, it remains active, buying is disabled, selling
  remains enabled, and provenance becomes `broker_position`.
- Without a position, it becomes inactive and both buying and selling are
  disabled.

This prevents the upstream watchlist from hiding or stranding an owned asset.

`UniverseReconciliationResult` reports imported, reactivated, removed,
buy-disabled, buy-reenabled, provenance-updated, and skipped symbols. Its
`changed` property covers material activation/trading changes.

## Tests

```bash
source .venv/bin/activate
pytest tests/test_universe.py -v
```
