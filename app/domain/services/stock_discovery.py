"""Stock discovery service for finding new investment opportunities."""

import logging
from typing import List, Optional

from app.domain.repositories.protocols import ISettingsRepository
from app.infrastructure.external.tradernet import TradernetClient

logger = logging.getLogger(__name__)


class StockDiscoveryService:
    """Service for discovering new stocks to add to the investment universe."""

    def __init__(
        self,
        tradernet_client: TradernetClient,
        settings_repo: ISettingsRepository,
    ):
        """
        Initialize stock discovery service.

        Args:
            tradernet_client: Tradernet client for fetching stock data
            settings_repo: Settings repository for discovery criteria
        """
        self._tradernet_client = tradernet_client
        self._settings_repo = settings_repo

    async def discover_candidates(self, existing_symbols: List[str]) -> List[dict]:
        """
        Discover candidate stocks that are not in the current universe.

        Args:
            existing_symbols: List of symbols already in the investment universe

        Returns:
            List of candidate stock dictionaries with symbol, exchange, volume, etc.
        """
        try:
            # Load discovery criteria from settings
            enabled = await self._settings_repo.get_float(
                "stock_discovery_enabled", 1.0
            )
            if enabled == 0.0:
                logger.info("Stock discovery is disabled")
                return []

            min_volume = await self._settings_repo.get_float(
                "stock_discovery_min_volume", 1000000.0
            )
            fetch_limit = int(
                await self._settings_repo.get_float("stock_discovery_fetch_limit", 50.0)
            )

            # Get geography and exchange filters
            geographies_str = await self._settings_repo.get("stock_discovery_geographies")
            if geographies_str is None:
                geographies_str = "EU,US,ASIA"
            geographies = [
                g.strip().upper() for g in geographies_str.split(",") if g.strip()
            ]

            exchanges_str = await self._settings_repo.get("stock_discovery_exchanges")
            if exchanges_str is None:
                exchanges_str = "usa,europe"
            exchanges = [e.strip().lower() for e in exchanges_str.split(",") if e.strip()]

            # Convert existing symbols to set for fast lookup
            existing_set = {s.upper() for s in existing_symbols}

            # Fetch candidates from Tradernet
            candidates = []
            for exchange in exchanges:
                try:
                    securities = self._tradernet_client.get_most_traded(
                        instrument_type="stock",
                        exchange=exchange,
                        gainers=False,
                        limit=fetch_limit,
                    )

                    # Filter candidates
                    for security in securities:
                        if not isinstance(security, dict):
                            continue

                        symbol = security.get("symbol", "").upper()
                        if not symbol:
                            continue

                        # Skip if already in universe
                        if symbol in existing_set:
                            continue

                        # Filter by geography (if available in security data)
                        security_country = security.get("country", "")
                        if security_country:
                            # Map country to geography
                            security_geo = self._country_to_geography(security_country)
                            if security_geo and security_geo not in geographies:
                                continue

                        # Filter by exchange
                        security_exchange = security.get("exchange", "").lower()
                        if security_exchange and security_exchange not in exchanges:
                            continue

                        # Filter by minimum volume
                        volume = security.get("volume", 0.0)
                        if isinstance(volume, (int, float)):
                            volume = float(volume)
                        else:
                            volume = 0.0

                        if volume < min_volume:
                            continue

                        # Add candidate
                        candidates.append(security)

                        # Respect fetch limit
                        if len(candidates) >= fetch_limit:
                            break

                    if len(candidates) >= fetch_limit:
                        break

                except Exception as e:
                    logger.warning(f"Failed to fetch securities from exchange {exchange}: {e}")
                    continue

            logger.info(f"Discovered {len(candidates)} candidate stocks")
            return candidates[:fetch_limit]  # Ensure we don't exceed limit

        except Exception as e:
            logger.error(f"Failed to discover stock candidates: {e}")
            return []

    def _country_to_geography(self, country: str) -> Optional[str]:
        """
        Map country code to geography.

        Args:
            country: Country code (e.g., "US", "DE", "CN")

        Returns:
            Geography code (EU, US, ASIA) or None
        """
        country_upper = country.upper()

        # US geography
        if country_upper in ("US", "USA", "UNITED STATES"):
            return "US"

        # EU geography (common EU countries)
        eu_countries = {
            "DE", "FR", "IT", "ES", "NL", "BE", "AT", "SE", "DK", "FI",
            "IE", "PT", "PL", "CZ", "GR", "HU", "RO", "BG", "HR", "SK",
            "SI", "LT", "LV", "EE", "LU", "MT", "CY",
        }
        if country_upper in eu_countries:
            return "EU"

        # ASIA geography (common Asian countries)
        asia_countries = {
            "CN", "JP", "KR", "IN", "SG", "HK", "TW", "MY", "TH", "VN",
            "ID", "PH", "PK", "BD", "LK", "MM", "KH", "LA",
        }
        if country_upper in asia_countries:
            return "ASIA"

        return None

