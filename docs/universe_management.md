# Universe Management & Security Import

**File**: `sentinel/universe.py`

## Overview

This module handles reconciliation between the Freedom24 "Favorites" list and Sentinel's security universe. It provides the infrastructure for importing, tracking, and managing securities from external sources.

## Key Features

### Freedom24 Integration

- Imports securities from Freedom24 "Favorites" watchlist
- Reconciles additions, removals, and modifications
- Tracks provenance (which list/source each security came from)

### Security Import Workflow

1. **Fetch**: Pull Favorites list from Freedom24 API
2. **Reconcile**: Compare against existing Sentinel universe
3. **Import**: Add new securities with proper metadata
4. **Reactivate**: Re-enable previously disabled securities
5. **Remove**: Optionally remove securities no longer in Favorites

## Data Structures

### `SecurityImportResult`

Individual security import outcome:

```python
@dataclass
class SecurityImportResult:
    symbol: str
    name: str
    prices_count: int
    re_enabled: bool
```

### `UniverseReconciliationResult`

Batch import summary:

```python
@dataclass
class UniverseReconciliationResult:
    imported: list[str]          # Newly added symbols
    reactivated: list[str]       # Re-enabled symbols
    removed: list[str]           # Removed symbols
    buy_disabled: list[str]      # Disabled for buying
    buy_reenabled: list[str]     # Re-enabled for buying
    provenance_updated: list[str] # Source list changed
    skipped: list[str]           # Already up-to-date

    @property
    def changed: bool           # True if any modifications made
```

## Universe Sources

### `FREEDOM24_UNIVERSE_SOURCE`

String identifier: `"freedom24_default"`

- Tracks securities from Freedom24 Favorites
- Used in `securities.provenance` field

### `BROKER_POSITION_UNIVERSE_SOURCE`

String identifier: `"broker_position"`

- Tracks securities that have active positions
- Auto-added when positions are synced from broker

## API Endpoints

Exposed via `sentinel/api/routers/securities.py`:

- `POST /api/securities/import-favorites` - Import from Freedom24
- `GET /api/securities/universe` - List all securities with provenance
- `PUT /api/securities/{symbol}/provenance` - Update security source

## Usage Examples

### Import Freedom24 Favorites

```python
from sentinel.universe import reconcile_favorites

result = await reconcile_favorites(broker, db)

print(f"Imported: {len(result.imported)}")
print(f"Reactivated: {len(result.reactivated)}")
print(f"Skipped: {len(result.skipped)}")
print(f"Changes made: {result.changed}")
```

### Check Security Provenance

```python
securities = await db.get_all_securities()

for sec in securities:
    print(f"{sec['symbol']}: {sec.get('provenance', 'unknown')}")
```

## Implementation Details

### Lot Size Detection

Extracts minimum lot size from broker metadata:

- Handles both direct `lot` field and nested structures
- Defaults to 1 if not specified
- Used for trade sizing calculations

### Market ID Extraction

Pulls market identifier from broker payload:

- Supports nested `mrkt.mkt_id` structure
- Falls back to existing DB value if broker returns None
- Empty string if no market info available

### Ticker Parsing

From Freedom24 stock list payload:

- Extracts from `tickers` array in default list
- Strips whitespace and filters empty strings
- Returns as `set[str]` for efficient lookup

## Reconciliation Logic

### Import Flow

1. Fetch current Favorites from broker
2. For each ticker in Favorites:
   - If not in DB → **Import** (add with provenance)
   - If exists but disabled → **Reactivate**
   - If exists and active → **Skip** (already tracked)
3. Optionally remove securities not in Favorites (user-configurable)

### Update Flow

1. Compare broker metadata with DB records
2. Update fields: `geography`, `industry`, `instr_kind_c`, `market_id`
3. Track which securities had changes in `provenance_updated`

## Testing

Tests located in `tests/test_universe.py`

Key test scenarios:

- Full reconciliation with new imports
- Reactivation of disabled securities
- Provenance tracking and updates
- Empty/edge case handling

## Related Documentation

- [API: Securities](../sentinel/api/routers/securities.py) - Endpoint implementation
- [Broker: API Wrapper](../sentinel/broker.py) - Freedom24 API integration
- [Database: Schema](../sentinel/database/base.py) - Securities table structure
