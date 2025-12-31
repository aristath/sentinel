"""Planner repository for holistic planner sequences and evaluations."""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.core.database.manager import get_db_manager
from app.modules.planning.domain.holistic_planner import ActionCandidate

logger = logging.getLogger(__name__)


class PlannerRepository:
    """Repository for planner database operations."""

    def __init__(self):
        self._db_manager = None

    async def _get_db(self):
        """Get planner database connection."""
        if self._db_manager is None:
            self._db_manager = get_db_manager()
        return self._db_manager.planner

    async def ensure_sequences_generated(
        self, portfolio_hash: str, sequences: List[List[ActionCandidate]]
    ) -> None:
        """
        Check if sequences exist for portfolio_hash, if not insert all sequences.

        Args:
            portfolio_hash: Portfolio hash
            sequences: List of sequences to insert (each is List[ActionCandidate])
        """
        db = await self._get_db()

        # Check if sequences already exist
        row = await db.fetchone(
            "SELECT COUNT(*) as count FROM sequences WHERE portfolio_hash = ?",
            (portfolio_hash,),
        )
        if row and row["count"] > 0:
            logger.debug(
                f"Sequences already exist for portfolio {portfolio_hash[:8]}..."
            )
            return

        # Insert all sequences
        now = datetime.now().isoformat()
        inserted = 0

        for sequence in sequences:
            if not sequence:
                continue

            # Calculate sequence hash
            sequence_repr = [(c.symbol, c.side, c.quantity) for c in sequence]
            sequence_json_str = json.dumps(sequence_repr, sort_keys=False)
            import hashlib

            sequence_hash = hashlib.md5(sequence_json_str.encode()).hexdigest()

            # Calculate priority (sum of action priorities)
            priority = sum(c.priority for c in sequence)

            # Determine pattern type (simplified - could be enhanced)
            pattern_type = self._determine_pattern_type(sequence)

            # Serialize sequence
            sequence_data = [
                {
                    "side": c.side,
                    "symbol": c.symbol,
                    "name": c.name,
                    "quantity": c.quantity,
                    "price": c.price,
                    "value_eur": c.value_eur,
                    "currency": c.currency,
                    "priority": c.priority,
                    "reason": c.reason,
                    "tags": c.tags,
                }
                for c in sequence
            ]
            sequence_json = json.dumps(sequence_data)

            await db.execute(
                """INSERT INTO sequences
                   (sequence_hash, portfolio_hash, priority, sequence_json, depth, pattern_type, completed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    sequence_hash,
                    portfolio_hash,
                    priority,
                    sequence_json,
                    len(sequence),
                    pattern_type,
                    now,
                ),
            )
            inserted += 1

        await db.commit()
        logger.info(
            f"Inserted {inserted} sequences for portfolio {portfolio_hash[:8]}..."
        )

    def _determine_pattern_type(self, sequence: List[ActionCandidate]) -> str:
        """Determine pattern type from sequence (simplified heuristic)."""
        if len(sequence) == 1:
            return "single_best"
        has_sell = any(c.side == "SELL" for c in sequence)
        has_buy = any(c.side == "BUY" for c in sequence)
        if has_sell and has_buy:
            return "mixed_strategy"
        elif has_sell:
            return "multi_sell"
        else:
            return "multi_buy"

    async def get_next_sequences(
        self, portfolio_hash: str, limit: int = 100
    ) -> List[Dict]:
        """
        Get next N sequences ordered by priority DESC, not completed.

        Args:
            portfolio_hash: Portfolio hash
            limit: Maximum number of sequences to return

        Returns:
            List of dicts with sequence_hash, sequence_json, priority, depth, pattern_type
        """
        db = await self._get_db()

        rows = await db.fetchall(
            """SELECT sequence_hash, sequence_json, priority, depth, pattern_type
               FROM sequences
               WHERE portfolio_hash = ? AND completed = 0
               ORDER BY priority DESC
               LIMIT ?""",
            (portfolio_hash, limit),
        )

        return [dict(row) for row in rows]

    async def mark_sequence_completed(
        self, sequence_hash: str, portfolio_hash: str, evaluated_at: str
    ) -> None:
        """
        Mark sequence as completed.

        Args:
            sequence_hash: Sequence hash
            portfolio_hash: Portfolio hash
            evaluated_at: ISO timestamp when evaluated
        """
        db = await self._get_db()

        await db.execute(
            """UPDATE sequences
               SET completed = 1, evaluated_at = ?
               WHERE sequence_hash = ? AND portfolio_hash = ?""",
            (evaluated_at, sequence_hash, portfolio_hash),
        )
        await db.commit()

    async def has_evaluation(self, sequence_hash: str, portfolio_hash: str) -> bool:
        """
        Check if evaluation exists for sequence.

        Args:
            sequence_hash: Sequence hash
            portfolio_hash: Portfolio hash

        Returns:
            True if evaluation exists, False otherwise
        """
        db = await self._get_db()

        row = await db.fetchone(
            "SELECT COUNT(*) as count FROM evaluations WHERE sequence_hash = ? AND portfolio_hash = ?",
            (sequence_hash, portfolio_hash),
        )

        return row and row["count"] > 0

    async def insert_evaluation(
        self,
        sequence_hash: str,
        portfolio_hash: str,
        end_score: float,
        breakdown: Dict,
        end_cash: float,
        end_context_positions: Dict[str, float],
        div_score: float,
        total_value: float,
    ) -> None:
        """
        Insert evaluation result.

        If evaluation already exists, skip insertion (avoids PRIMARY KEY violation).

        Args:
            sequence_hash: Sequence hash
            portfolio_hash: Portfolio hash
            end_score: Final portfolio score
            breakdown: Score breakdown dict
            end_cash: Cash remaining after sequence
            end_context_positions: Final positions dict
            div_score: Diversification score
            total_value: Total portfolio value
        """
        # Check if evaluation already exists
        if await self.has_evaluation(sequence_hash, portfolio_hash):
            logger.debug(
                f"Evaluation already exists for sequence {sequence_hash[:8]}, skipping insertion"
            )
            return

        db = await self._get_db()
        now = datetime.now().isoformat()

        await db.execute(
            """INSERT INTO evaluations
               (sequence_hash, portfolio_hash, end_score, breakdown_json, end_cash,
                end_context_positions_json, div_score, total_value, evaluated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sequence_hash,
                portfolio_hash,
                end_score,
                json.dumps(breakdown),
                end_cash,
                json.dumps(end_context_positions),
                div_score,
                total_value,
                now,
            ),
        )
        await db.commit()

    async def get_best_result(self, portfolio_hash: str) -> Optional[Dict]:
        """
        Get best result from best_result table.

        Args:
            portfolio_hash: Portfolio hash

        Returns:
            Dict with best_sequence_hash, best_score, updated_at or None
        """
        db = await self._get_db()

        row = await db.fetchone(
            "SELECT best_sequence_hash, best_score, updated_at FROM best_result WHERE portfolio_hash = ?",
            (portfolio_hash,),
        )

        if row:
            return dict(row)
        return None

    async def update_best_result(
        self, portfolio_hash: str, sequence_hash: str, score: float
    ) -> None:
        """
        Insert or update best_result table.

        Args:
            portfolio_hash: Portfolio hash
            sequence_hash: Best sequence hash
            score: Best score
        """
        db = await self._get_db()
        now = datetime.now().isoformat()

        await db.execute(
            """INSERT OR REPLACE INTO best_result
               (portfolio_hash, best_sequence_hash, best_score, updated_at)
               VALUES (?, ?, ?, ?)""",
            (portfolio_hash, sequence_hash, score, now),
        )
        await db.commit()

    async def delete_sequences_only(self, portfolio_hash: str) -> None:
        """
        Delete sequences only (keep evaluations and best_result).

        Used when regenerating sequences with new settings - evaluations
        are still valid and can be reused if sequences overlap.

        Args:
            portfolio_hash: Portfolio hash
        """
        db = await self._get_db()

        await db.execute(
            "DELETE FROM sequences WHERE portfolio_hash = ?", (portfolio_hash,)
        )
        await db.commit()

        logger.info(
            f"Deleted sequences (kept evaluations) for portfolio {portfolio_hash[:8]}..."
        )

    async def delete_sequences_for_portfolio(self, portfolio_hash: str) -> None:
        """
        Delete all sequences, evaluations, and best_result for portfolio_hash.

        Args:
            portfolio_hash: Portfolio hash
        """
        db = await self._get_db()

        await db.execute(
            "DELETE FROM sequences WHERE portfolio_hash = ?", (portfolio_hash,)
        )
        await db.execute(
            "DELETE FROM evaluations WHERE portfolio_hash = ?", (portfolio_hash,)
        )
        await db.execute(
            "DELETE FROM best_result WHERE portfolio_hash = ?", (portfolio_hash,)
        )
        await db.commit()

        logger.info(f"Deleted all planner data for portfolio {portfolio_hash[:8]}...")

    async def has_sequences(self, portfolio_hash: str) -> bool:
        """
        Check if sequences exist for portfolio_hash.

        Args:
            portfolio_hash: Portfolio hash

        Returns:
            True if sequences exist, False otherwise
        """
        db = await self._get_db()

        row = await db.fetchone(
            "SELECT COUNT(*) as count FROM sequences WHERE portfolio_hash = ?",
            (portfolio_hash,),
        )

        return row and row["count"] > 0

    async def get_evaluation_count(self, portfolio_hash: str) -> int:
        """
        Get count of evaluated sequences for portfolio.

        Args:
            portfolio_hash: Portfolio hash

        Returns:
            Number of evaluated sequences
        """
        db = await self._get_db()

        row = await db.fetchone(
            "SELECT COUNT(*) as count FROM evaluations WHERE portfolio_hash = ?",
            (portfolio_hash,),
        )

        return row["count"] if row else 0

    async def get_total_sequence_count(self, portfolio_hash: str) -> int:
        """
        Get total count of sequences for portfolio.

        Args:
            portfolio_hash: Portfolio hash

        Returns:
            Total number of sequences
        """
        db = await self._get_db()

        row = await db.fetchone(
            "SELECT COUNT(*) as count FROM sequences WHERE portfolio_hash = ?",
            (portfolio_hash,),
        )

        return row["count"] if row else 0

    async def are_all_sequences_evaluated(self, portfolio_hash: str) -> bool:
        """
        Check if all sequences for portfolio_hash have been evaluated.

        Args:
            portfolio_hash: Portfolio hash

        Returns:
            True if all sequences are evaluated, False otherwise
        """
        db = await self._get_db()

        row = await db.fetchone(
            """SELECT COUNT(*) as total, SUM(completed) as completed
               FROM sequences WHERE portfolio_hash = ?""",
            (portfolio_hash,),
        )

        if not row or row["total"] == 0:
            return False

        return row["completed"] == row["total"]

    async def get_best_sequence_from_hash(
        self, portfolio_hash: str, sequence_hash: str
    ) -> Optional[List[ActionCandidate]]:
        """
        Get sequence from hash and deserialize to List[ActionCandidate].

        Args:
            portfolio_hash: Portfolio hash
            sequence_hash: Sequence hash

        Returns:
            List[ActionCandidate] or None if not found
        """
        db = await self._get_db()

        row = await db.fetchone(
            "SELECT sequence_json FROM sequences WHERE sequence_hash = ? AND portfolio_hash = ?",
            (sequence_hash, portfolio_hash),
        )

        if not row:
            return None

        sequence_data = json.loads(row["sequence_json"])

        return [
            ActionCandidate(
                side=c["side"],
                symbol=c["symbol"],
                name=c["name"],
                quantity=c["quantity"],
                price=c["price"],
                value_eur=c["value_eur"],
                currency=c["currency"],
                priority=c["priority"],
                reason=c["reason"],
                tags=c["tags"],
            )
            for c in sequence_data
        ]
