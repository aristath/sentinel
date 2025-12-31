"""Universe pruning job.

Automatically removes low-quality stocks from the investment universe
based on consistently low scores over a configurable time period.
"""

import logging

from app.infrastructure.external.tradernet import get_tradernet_client
from app.repositories import ScoreRepository, SecurityRepository, SettingsRepository

logger = logging.getLogger(__name__)


async def prune_universe() -> None:
    """
    Automatically prune stocks from the universe based on configurable criteria.

    Process:
    1. Get all active stocks
    2. For each stock:
       - Get recent scores (within configured months window)
       - Check if average score is below threshold
       - Check if minimum samples requirement is met
       - Optionally check if stock is delisted
    3. Mark stocks as inactive if criteria are met
    """
    logger.info("Starting universe pruning...")

    try:
        # Get dependencies
        security_repo = SecurityRepository()
        score_repo = ScoreRepository()
        settings_repo = SettingsRepository()

        # Get pruning settings
        enabled = await settings_repo.get_float("universe_pruning_enabled", 1.0)
        if enabled == 0.0:
            logger.info("Universe pruning is disabled, skipping")
            return

        score_threshold = await settings_repo.get_float(
            "universe_pruning_score_threshold", 0.50
        )
        months = await settings_repo.get_float("universe_pruning_months", 3.0)
        min_samples = int(
            await settings_repo.get_float("universe_pruning_min_samples", 2.0)
        )
        check_delisted = (
            await settings_repo.get_float("universe_pruning_check_delisted", 1.0) == 1.0
        )

        logger.info(
            f"Pruning criteria: threshold={score_threshold}, months={months}, "
            f"min_samples={min_samples}, check_delisted={check_delisted}"
        )

        # Get all active stocks
        stocks = await security_repo.get_all_active()
        logger.info(f"Checking {len(stocks)} active stocks for pruning")

        if not stocks:
            logger.info("No active stocks to check")
            return

        client = get_tradernet_client()
        if check_delisted and not client.is_connected:
            if not client.connect():
                logger.warning(
                    "Failed to connect to Tradernet for delisted check, "
                    "skipping delisted detection"
                )
                check_delisted = False

        pruned_count = 0

        for stock in stocks:
            try:
                # Get recent scores
                scores = await score_repo.get_recent_scores(stock.symbol, months)

                # Check minimum samples requirement
                if len(scores) < min_samples:
                    logger.debug(
                        f"Stock {stock.symbol}: only {len(scores)} score(s), "
                        f"below minimum {min_samples}, skipping"
                    )
                    continue

                # Calculate average score
                total_scores = [
                    s.total_score for s in scores if s.total_score is not None
                ]
                if not total_scores:
                    logger.debug(
                        f"Stock {stock.symbol}: no valid scores found, skipping"
                    )
                    continue

                avg_score = sum(total_scores) / len(total_scores)

                # Check if average score is below threshold
                if avg_score >= score_threshold:
                    logger.debug(
                        f"Stock {stock.symbol}: average score {avg_score:.3f} "
                        f"above threshold {score_threshold}, keeping"
                    )
                    continue

                # Check if stock is delisted (if enabled)
                is_delisted = False
                if check_delisted:
                    try:
                        # Try to get security info - if it fails or returns None, might be delisted
                        security_info = client.get_security_info(stock.symbol)
                        if security_info is None:
                            logger.info(
                                f"Stock {stock.symbol}: security info not found, "
                                f"possibly delisted"
                            )
                            is_delisted = True
                        else:
                            # Try to get a quote - if it fails, might be delisted
                            quote = client.get_quote(stock.symbol)
                            if quote is None or not hasattr(quote, "price"):
                                logger.info(
                                    f"Stock {stock.symbol}: quote not available, "
                                    f"possibly delisted"
                                )
                                is_delisted = True
                    except Exception as e:
                        logger.warning(
                            f"Error checking if {stock.symbol} is delisted: {e}"
                        )
                        # Don't prune based on delisted check if there's an error
                        is_delisted = False

                # Prune if criteria met (low score, or delisted if check enabled)
                if is_delisted or avg_score < score_threshold:
                    reason = (
                        "delisted" if is_delisted else f"low score ({avg_score:.3f})"
                    )
                    logger.info(
                        f"Pruning stock {stock.symbol}: {reason} "
                        f"(threshold: {score_threshold}, samples: {len(scores)})"
                    )
                    # Mark as inactive rather than delete to preserve historical data
                    await security_repo.mark_inactive(stock.symbol)
                    pruned_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing stock {stock.symbol} for pruning: {e}",
                    exc_info=True,
                )
                # Continue with next stock
                continue

        logger.info(
            f"Universe pruning complete: {pruned_count} stock(s) pruned out of {len(stocks)} checked"
        )

    except Exception as e:
        logger.error(f"Error in universe pruning job: {e}", exc_info=True)
