"""Stock discovery job.

Automatically discovers and adds high-quality stocks to the investment universe
based on conservative criteria and user-configurable settings.
"""

import logging

from app.application.services.scoring_service import ScoringService
from app.domain.models import Stock
from app.domain.services.stock_discovery import StockDiscoveryService
from app.domain.services.symbol_resolver import SymbolResolver
from app.domain.value_objects.currency import Currency
from app.infrastructure.database.manager import get_db_manager
from app.infrastructure.external.tradernet import get_tradernet_client
from app.repositories import ScoreRepository, SettingsRepository, StockRepository

logger = logging.getLogger(__name__)


async def discover_new_stocks() -> None:
    """
    Discover and add new stocks to the investment universe.

    Process:
    1. Check if discovery is enabled
    2. Get existing universe symbols
    3. Use StockDiscoveryService to find candidates
    4. Score each candidate using ScoringService
    5. Filter by score threshold
    6. Sort by score (best first)
    7. Enforce monthly limit (max_per_month)
    8. Add stocks to universe (or flag for review if require_manual_review is true)
    """
    logger.info("Starting stock discovery...")

    try:
        # Get dependencies
        settings_repo = SettingsRepository()
        stock_repo = StockRepository()
        # Note: Direct DB access here is a known architecture violation.
        # This job needs to coordinate multiple operations. See README.md Architecture section for details.
        db_manager = get_db_manager()

        # Check if discovery is enabled
        enabled = await settings_repo.get_float("stock_discovery_enabled", 1.0)
        if enabled == 0.0:
            logger.info("Stock discovery is disabled, skipping")
            return

        # Get discovery settings
        score_threshold = await settings_repo.get_float(
            "stock_discovery_score_threshold", 0.75
        )
        max_per_month = int(
            await settings_repo.get_float("stock_discovery_max_per_month", 2.0)
        )
        require_manual_review = (
            await settings_repo.get_float("stock_discovery_require_manual_review", 0.0)
            == 1.0
        )

        # Get existing universe symbols
        existing_stocks = await stock_repo.get_all_active()
        existing_symbols = [s.symbol for s in existing_stocks]

        # Initialize discovery service
        tradernet_client = get_tradernet_client()
        discovery_service = StockDiscoveryService(
            tradernet_client=tradernet_client,
            settings_repo=settings_repo,
        )

        # Find candidates
        candidates = await discovery_service.discover_candidates(
            existing_symbols=existing_symbols
        )

        if not candidates:
            logger.info("No new candidates found")
            return

        logger.info(f"Found {len(candidates)} candidate stocks")

        # Initialize scoring service and symbol resolver
        score_repo = ScoreRepository()
        scoring_service = ScoringService(
            stock_repo=stock_repo,
            score_repo=score_repo,
            db_manager=db_manager,
        )
        symbol_resolver = SymbolResolver(
            tradernet_client=tradernet_client,
            stock_repo=stock_repo,
        )

        # Score candidates and collect results
        scored_candidates = []
        for candidate in candidates:
            symbol = candidate.get("symbol", "").upper()
            if not symbol:
                continue

            try:
                # Resolve symbol to get ISIN for Yahoo Finance lookups
                symbol_info = await symbol_resolver.resolve(symbol)
                if symbol_info.isin:
                    logger.info(f"Resolved {symbol} -> ISIN: {symbol_info.isin}")
                    candidate["isin"] = symbol_info.isin

                # Score the candidate using ISIN for Yahoo lookups if available
                score = await scoring_service.calculate_and_save_score(
                    symbol=symbol,
                    yahoo_symbol=symbol_info.yahoo_symbol,
                    country=candidate.get("country"),
                    industry=candidate.get("industry"),
                )

                if score and score.total_score is not None:
                    scored_candidates.append((candidate, score.total_score))
                else:
                    logger.warning(
                        f"Failed to score {symbol}: score calculation returned None"
                    )
            except Exception as e:
                logger.warning(f"Failed to score {symbol}: {e}")
                continue

        if not scored_candidates:
            logger.info("No candidates passed scoring")
            return

        # Filter by score threshold
        above_threshold = [
            (candidate, score)
            for candidate, score in scored_candidates
            if score >= score_threshold
        ]

        if not above_threshold:
            logger.info(f"No candidates above score threshold {score_threshold}")
            return

        logger.info(
            f"{len(above_threshold)} candidates above threshold {score_threshold}"
        )

        # Sort by score (best first)
        above_threshold.sort(key=lambda x: x[1], reverse=True)

        # Enforce monthly limit
        to_add = above_threshold[:max_per_month]

        if require_manual_review:
            logger.info(
                f"Manual review required: {len(to_add)} stocks flagged for review"
            )
            for candidate, candidate_score in to_add:
                logger.info(
                    f"  - {candidate.get('symbol')}: score={candidate_score:.3f} (flagged for review)"
                )
            return

        # Add stocks to universe
        added_count = 0
        for candidate, candidate_score in to_add:
            symbol = candidate.get("symbol", "").upper()
            name = candidate.get("name", symbol)
            country = candidate.get("country")
            industry = candidate.get("industry")
            isin = candidate.get("isin")  # ISIN resolved earlier

            try:
                # Check if stock already exists (shouldn't, but be safe)
                existing = await stock_repo.get_by_symbol(symbol)
                if existing:
                    logger.warning(f"Stock {symbol} already exists, skipping")
                    continue

                # Create stock object with ISIN for Yahoo Finance lookups
                stock = Stock(
                    symbol=symbol,
                    name=name,
                    country=country,
                    industry=industry,
                    isin=isin,  # Store ISIN for future Yahoo lookups
                    currency=Currency.EUR,  # Default, will be updated during sync
                    active=True,
                    allow_buy=True,
                    allow_sell=False,  # Conservative: don't allow selling initially
                )

                # Add to universe
                await stock_repo.create(stock)
                logger.info(
                    f"Added stock {symbol} ({name}) with score {candidate_score:.3f}"
                    + (f", ISIN: {isin}" if isin else "")
                )
                added_count += 1

            except Exception as e:
                logger.error(f"Failed to add stock {symbol}: {e}")
                continue

        logger.info(f"Stock discovery complete: {added_count} stocks added")

    except Exception as e:
        logger.error(f"Stock discovery failed: {e}", exc_info=True)
