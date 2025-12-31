"""Security repository - CRUD operations for securities table."""

from datetime import datetime
from typing import List, Optional

from app.core.database.manager import get_db_manager
from app.domain.models import Security
from app.domain.value_objects.product_type import ProductType
from app.repositories.base import transaction_context


class SecurityRepository:
    """Repository for security universe operations."""

    def __init__(self, db=None):
        """Initialize repository.

        Args:
            db: Optional database connection for testing. If None, uses get_db_manager().config
                Can be a Database instance or raw aiosqlite.Connection (will be wrapped)
        """
        if db is not None:
            # If it's a raw connection without fetchone/fetchall, wrap it
            if not hasattr(db, "fetchone") and hasattr(db, "execute"):
                from app.repositories.base import DatabaseAdapter

                self._db = DatabaseAdapter(db)
            else:
                self._db = db
        else:
            self._db = get_db_manager().config

    async def get_by_symbol(self, symbol: str) -> Optional[Security]:
        """Get security by symbol."""
        row = await self._db.fetchone(
            "SELECT * FROM securities WHERE symbol = ?", (symbol.upper(),)
        )
        if not row:
            return None
        return self._row_to_security(row)

    async def get_by_isin(self, isin: str) -> Optional[Security]:
        """Get security by ISIN."""
        row = await self._db.fetchone(
            "SELECT * FROM securities WHERE isin = ?", (isin.upper(),)
        )
        if not row:
            return None
        return self._row_to_security(row)

    async def get_by_identifier(self, identifier: str) -> Optional[Security]:
        """Get security by symbol or ISIN.

        Checks if identifier looks like an ISIN (12 chars, starts with 2 letters)
        and queries accordingly.

        Args:
            identifier: Security symbol or ISIN

        Returns:
            Security if found, None otherwise
        """
        identifier = identifier.strip().upper()

        # Check if it looks like an ISIN (12 chars, country code + alphanumeric)
        if len(identifier) == 12 and identifier[:2].isalpha():
            sec = await self.get_by_isin(identifier)
            if sec:
                return sec

        # Try symbol lookup
        return await self.get_by_symbol(identifier)

    async def get_all_active(self) -> List[Security]:
        """Get all active securities."""
        rows = await self._db.fetchall("SELECT * FROM securities WHERE active = 1")
        return [self._row_to_security(row) for row in rows]

    async def get_all(self) -> List[Security]:
        """Get all securities (active and inactive)."""
        rows = await self._db.fetchall("SELECT * FROM securities")
        return [self._row_to_security(row) for row in rows]

    async def create(self, security: Security) -> None:
        """Create a new security."""
        now = datetime.now().isoformat()
        async with transaction_context(self._db) as conn:
            await conn.execute(
                """
                INSERT INTO securities
                (symbol, yahoo_symbol, isin, name, product_type, industry, country, fullExchangeName,
                 priority_multiplier, min_lot, active, allow_buy, allow_sell,
                 currency, min_portfolio_target, max_portfolio_target,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    security.symbol.upper(),
                    security.yahoo_symbol,
                    security.isin,
                    security.name,
                    security.product_type.value if security.product_type else None,
                    security.industry,
                    security.country,
                    security.fullExchangeName,
                    security.priority_multiplier,
                    security.min_lot,
                    1 if security.active else 0,
                    1 if security.allow_buy else 0,
                    1 if security.allow_sell else 0,
                    security.currency,
                    security.min_portfolio_target,
                    security.max_portfolio_target,
                    now,
                    now,
                ),
            )

    async def update(self, symbol: str, **updates) -> None:
        """Update security fields.

        Args:
            symbol: Security symbol to update
            **updates: Field name -> value mappings to update

        Raises:
            ValueError: If any update key is not in allowed fields
        """
        if not updates:
            return

        # Whitelist of allowed update fields for security
        ALLOWED_UPDATE_FIELDS = {
            "active",
            "allow_buy",
            "allow_sell",
            "updated_at",
            "name",
            "product_type",
            "sector",
            "industry",
            "country",
            "fullExchangeName",
            "currency",
            "exchange",
            "market_cap",
            "pe_ratio",
            "dividend_yield",
            "beta",
            "52w_high",
            "52w_low",
            "min_portfolio_target",
            "max_portfolio_target",
            "isin",
            "min_lot",
            "priority_multiplier",
            "yahoo_symbol",
        }

        # Validate all keys are in whitelist
        invalid_keys = set(updates.keys()) - ALLOWED_UPDATE_FIELDS
        if invalid_keys:
            raise ValueError(f"Invalid update fields: {invalid_keys}")

        now = datetime.now().isoformat()
        updates["updated_at"] = now

        # Convert booleans to integers
        for key in ("active", "allow_buy", "allow_sell"):
            if key in updates:
                updates[key] = 1 if updates[key] else 0

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [symbol.upper()]

        async with transaction_context(self._db) as conn:
            await conn.execute(
                f"UPDATE securities SET {set_clause} WHERE symbol = ?", values
            )

    async def delete(self, symbol: str) -> None:
        """Soft delete a security (set active=False)."""
        await self.update(symbol, active=False)

    async def mark_inactive(self, symbol: str) -> None:
        """Mark a security as inactive (alias for delete/soft-delete)."""
        await self.update(symbol, active=False)

    async def get_with_scores(self) -> List[dict]:
        """Get all active securities with their scores and positions.

        Note: This method directly accesses multiple databases (config.db and state.db)
        which violates the repository pattern. This is a known architecture violation
        documented in README.md Architecture section. A future refactoring could:
        1. Create a composite repository/service that orchestrates multiple repositories
        2. Inject ScoreRepository and PositionRepository as dependencies
        3. Move this logic to an application service layer

        For now, this approach is pragmatic as it allows efficient multi-database queries
        without requiring significant architectural changes.
        """
        db_manager = get_db_manager()

        # Fetch securities from config.db
        security_rows = await self._db.fetchall(
            "SELECT * FROM securities WHERE active = 1"
        )
        securities = {
            row["symbol"]: {key: row[key] for key in row.keys()}
            for row in security_rows
        }

        # Fetch scores from calculations.db
        score_rows = await db_manager.calculations.fetchall("SELECT * FROM scores")
        scores = {
            row["symbol"]: {key: row[key] for key in row.keys()} for row in score_rows
        }

        # Fetch positions from state.db
        position_rows = await db_manager.state.fetchall("SELECT * FROM positions")
        positions = {
            row["symbol"]: {key: row[key] for key in row.keys()}
            for row in position_rows
        }

        # Merge data
        result = []
        for symbol, security in securities.items():
            # Add score data
            if symbol in scores:
                score = scores[symbol]
                security["total_score"] = score.get("total_score")
                security["quality_score"] = score.get("quality_score")
                security["opportunity_score"] = score.get("opportunity_score")
                security["analyst_score"] = score.get("analyst_score")
                security["allocation_fit_score"] = score.get("allocation_fit_score")
                security["volatility"] = score.get("volatility")
                security["calculated_at"] = score.get("calculated_at")

            # Add position data
            if symbol in positions:
                pos = positions[symbol]
                security["position_value"] = pos.get("market_value_eur") or 0
                security["quantity"] = pos.get("quantity") or 0
                security["avg_price"] = pos.get("avg_price")
                security["current_price"] = pos.get("current_price")
            else:
                security["position_value"] = 0
                security["quantity"] = 0

            result.append(security)

        return result

    def _row_to_security(self, row) -> Security:
        """Convert database row to Security model."""
        keys = row.keys()

        # Extract product_type from database row
        product_type = None
        if "product_type" in keys and row["product_type"]:
            product_type = ProductType.from_string(row["product_type"])

        return Security(
            symbol=row["symbol"],
            yahoo_symbol=row["yahoo_symbol"],
            isin=row["isin"] if "isin" in keys else None,
            name=row["name"],
            product_type=product_type,
            industry=row["industry"],
            country=row["country"] if "country" in keys else None,
            fullExchangeName=(
                row["fullExchangeName"] if "fullExchangeName" in keys else None
            ),
            priority_multiplier=row["priority_multiplier"] or 1.0,
            min_lot=row["min_lot"] or 1,
            active=bool(row["active"]),
            allow_buy=bool(row["allow_buy"]) if row["allow_buy"] is not None else True,
            allow_sell=(
                bool(row["allow_sell"]) if row["allow_sell"] is not None else False
            ),
            currency=row["currency"],
            last_synced=row["last_synced"] if "last_synced" in keys else None,
            min_portfolio_target=(
                row["min_portfolio_target"]
                if "min_portfolio_target" in keys
                and row["min_portfolio_target"] is not None
                else None
            ),
            max_portfolio_target=(
                row["max_portfolio_target"]
                if "max_portfolio_target" in keys
                and row["max_portfolio_target"] is not None
                else None
            ),
        )
