# Deprecation Timeline

This document tracks deprecated features and their removal timeline.

## Stock → Security Refactoring

### Overview

The codebase has been refactored to use "Security" terminology instead of "Stock" to better support multiple product types (equities, ETFs, ETCs, mutual funds).

### Backward Compatibility Aliases

The following type aliases were added to maintain backward compatibility during the transition:

- `Stock = Security` (in `app/domain/models.py`)
- `StockScore = SecurityScore` (in `app/domain/models.py`)
- `StockPriority = SecurityPriority` (in `app/domain/models.py`)
- `StockAddedEvent = SecurityAddedEvent` (in `app/domain/events/__init__.py`)
- `StockRepository = SecurityRepository` (in `app/repositories/__init__.py`)

### Deprecation Schedule

**Status:** ⚠️ DEPRECATED (as of January 2025)

**Removal Timeline:**

| Date | Milestone | Action |
|------|-----------|--------|
| January 2025 | Initial refactoring | Aliases introduced for backward compatibility |
| March 2025 | Deprecation warnings | Add deprecation warnings to alias usage |
| June 2025 | **REMOVAL** | All backward compatibility aliases removed |

### Migration Path

**For external code using these aliases:**

1. **Before March 2025**: Update all references:
   - `Stock` → `Security`
   - `StockScore` → `SecurityScore`
   - `StockPriority` → `SecurityPriority`
   - `StockAddedEvent` → `SecurityAddedEvent`
   - `StockRepository` → `SecurityRepository`

2. **After March 2025**: Deprecation warnings will be logged for any usage of aliases

3. **June 2025**: Aliases will be completely removed from codebase

### Why Remove Aliases?

1. **Code clarity**: Single consistent terminology reduces confusion
2. **Type safety**: Eliminates duplicate type names that can cause mypy issues
3. **Maintainability**: Fewer aliases means simpler codebase
4. **Performance**: Minor reduction in import resolution overhead

### What About Internal References?

**All internal code** has been updated to use the new `Security` terminology. The aliases exist **only** for:
- Backward compatibility during transition period
- External tools/scripts that may reference the old names
- Any remaining test fixtures that haven't been updated

### How to Check for Deprecated Usage

```bash
# Search for deprecated alias usage in your code
grep -r "Stock[^a-z]" app/ --include="*.py" | grep -v "# Backward compatibility"

# Search for StockScore usage
grep -r "StockScore" app/ --include="*.py"

# Search for StockRepository usage
grep -r "StockRepository" app/ --include="*.py"
```

### Deprecation Warnings (Coming March 2025)

Starting March 2025, using deprecated aliases will log warnings:

```python
import warnings

class _DeprecatedStockAlias:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Stock is deprecated, use Security instead. "
            "Stock alias will be removed in June 2025.",
            DeprecationWarning,
            stacklevel=2
        )
        return Security(*args, **kwargs)

Stock = _DeprecatedStockAlias
```

## Other Deprecated Features

_(None currently)_

## Questions?

For questions about deprecations, please:
1. Check this document first
2. Review `docs/MIGRATION_GUIDE.md` for migration procedures
3. Open an issue at https://github.com/aristath/portfolioManager/issues
