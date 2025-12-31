"""Grouping repository - operations for country_groups and industry_groups tables."""

from datetime import datetime
from typing import Dict, List

from app.core.database import get_db_manager
from app.repositories.base import transaction_context


class GroupingRepository:
    """Repository for custom grouping operations."""

    def __init__(self, db=None):
        """Initialize repository.

        Args:
            db: Optional database connection for testing. If None, uses get_db_manager().config
        """
        if db is not None:
            if not hasattr(db, "fetchone") and hasattr(db, "execute"):
                from app.repositories.base import DatabaseAdapter

                self._db = DatabaseAdapter(db)
            else:
                self._db = db
        else:
            self._db = get_db_manager().config

    async def get_country_groups(self) -> Dict[str, List[str]]:
        """Get all country groups as dict mapping group_name -> [country_names]."""
        rows = await self._db.fetchall(
            "SELECT group_name, country_name FROM country_groups ORDER BY group_name, country_name"
        )
        groups: Dict[str, List[str]] = {}
        for row in rows:
            group_name = row["group_name"]
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(row["country_name"])
        return groups

    async def get_industry_groups(self) -> Dict[str, List[str]]:
        """Get all industry groups as dict mapping group_name -> [industry_names]."""
        rows = await self._db.fetchall(
            "SELECT group_name, industry_name FROM industry_groups ORDER BY group_name, industry_name"
        )
        groups: Dict[str, List[str]] = {}
        for row in rows:
            group_name = row["group_name"]
            industry_name = row["industry_name"]
            if group_name not in groups:
                groups[group_name] = []
            # Filter out the special __EMPTY__ marker
            if industry_name != "__EMPTY__":
                groups[group_name].append(industry_name)
        return groups

    async def set_country_group(
        self, group_name: str, country_names: List[str]
    ) -> None:
        """Set countries for a country group (replaces existing)."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            # Delete existing mappings for this group
            await conn.execute(
                "DELETE FROM country_groups WHERE group_name = ?", (group_name,)
            )

            # Insert new mappings
            # If empty list, insert a special marker to indicate group exists but is empty
            # This allows us to distinguish "deleted hardcoded group" from "never existed"
            if not country_names:
                await conn.execute(
                    """
                    INSERT INTO country_groups (group_name, country_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (group_name, "__EMPTY__", now, now),
                )
            else:
                for country_name in country_names:
                    await conn.execute(
                        """
                        INSERT INTO country_groups (group_name, country_name, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (group_name, country_name, now, now),
                    )

    async def set_industry_group(
        self, group_name: str, industry_names: List[str]
    ) -> None:
        """Set industries for an industry group (replaces existing)."""
        now = datetime.now().isoformat()

        async with transaction_context(self._db) as conn:
            # Delete existing mappings for this group
            await conn.execute(
                "DELETE FROM industry_groups WHERE group_name = ?", (group_name,)
            )

            # Insert new mappings
            # If empty list, insert a special marker to indicate group exists but is empty
            # This allows us to distinguish "deleted hardcoded group" from "never existed"
            if not industry_names:
                await conn.execute(
                    """
                    INSERT INTO industry_groups (group_name, industry_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (group_name, "__EMPTY__", now, now),
                )
            else:
                for industry_name in industry_names:
                    await conn.execute(
                        """
                        INSERT INTO industry_groups (group_name, industry_name, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (group_name, industry_name, now, now),
                    )

    async def delete_country_group(self, group_name: str) -> None:
        """Delete a country group."""
        async with transaction_context(self._db) as conn:
            await conn.execute(
                "DELETE FROM country_groups WHERE group_name = ?", (group_name,)
            )

    async def delete_industry_group(self, group_name: str) -> None:
        """Delete an industry group."""
        async with transaction_context(self._db) as conn:
            await conn.execute(
                "DELETE FROM industry_groups WHERE group_name = ?", (group_name,)
            )

    async def get_available_countries(self) -> List[str]:
        """Get list of all unique countries from securities table."""
        rows = await self._db.fetchall(
            "SELECT DISTINCT country FROM securities WHERE country IS NOT NULL AND country != '' ORDER BY country"
        )
        return [row["country"] for row in rows]

    async def get_available_industries(self) -> List[str]:
        """Get list of all unique industries from securities table."""
        rows = await self._db.fetchall(
            "SELECT DISTINCT industry FROM securities WHERE industry IS NOT NULL AND industry != '' ORDER BY industry"
        )
        return [row["industry"] for row in rows]
