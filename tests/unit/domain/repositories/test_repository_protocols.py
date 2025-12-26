"""Tests for repository protocols."""


class TestRepositoryProtocols:
    """Test that repository protocols are properly defined."""

    def test_stock_repository_protocol(self):
        """Test that StockRepository implements IStockRepository."""
        from app.repositories.stock import StockRepository

        # Check that the class has the required protocol methods
        assert hasattr(StockRepository, "get_by_symbol")
        assert hasattr(StockRepository, "get_all")
        assert hasattr(StockRepository, "get_all_active")
        assert hasattr(StockRepository, "create")
        assert hasattr(StockRepository, "update")
        assert hasattr(StockRepository, "delete")

    def test_position_repository_protocol(self):
        """Test that PositionRepository implements IPositionRepository."""
        from app.repositories.position import PositionRepository

        # Check that the class has the required protocol methods
        assert hasattr(PositionRepository, "get_by_symbol")
        assert hasattr(PositionRepository, "get_all")
        assert hasattr(PositionRepository, "upsert")

    def test_trade_repository_protocol(self):
        """Test that TradeRepository implements ITradeRepository."""
        from app.repositories.trade import TradeRepository

        # Check that the class has the required protocol methods
        assert hasattr(TradeRepository, "create")
        assert hasattr(TradeRepository, "get_by_order_id")
        assert hasattr(TradeRepository, "exists")

    def test_settings_repository_protocol(self):
        """Test that SettingsRepository implements ISettingsRepository."""
        from app.repositories.settings import SettingsRepository

        # Check that the class has the required protocol methods
        assert hasattr(SettingsRepository, "get")
        assert hasattr(SettingsRepository, "set")
        assert hasattr(SettingsRepository, "get_all")
        assert hasattr(SettingsRepository, "get_float")
        assert hasattr(SettingsRepository, "get_int")
        assert hasattr(SettingsRepository, "get_bool")
