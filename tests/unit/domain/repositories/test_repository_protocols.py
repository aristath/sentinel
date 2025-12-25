"""Tests for repository protocols."""

import pytest
from typing import Protocol
from app.domain.repositories.protocols import (
    IStockRepository,
    IPositionRepository,
    ITradeRepository,
    ISettingsRepository,
)
from app.domain.models import Stock, Position, Trade
from app.domain.value_objects.currency import Currency


class TestRepositoryProtocols:
    """Test that repository protocols are properly defined."""

    def test_stock_repository_protocol(self):
        """Test that StockRepository implements IStockRepository."""
        from app.repositories.stock import StockRepository
        
        # This is a structural check - if StockRepository doesn't implement
        # the protocol, mypy/type checker would catch it
        repo: IStockRepository = StockRepository()
        assert hasattr(repo, 'get_by_symbol')
        assert hasattr(repo, 'get_all')
        assert hasattr(repo, 'get_all_active')
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'update')
        assert hasattr(repo, 'delete')

    def test_position_repository_protocol(self):
        """Test that PositionRepository implements IPositionRepository."""
        from app.repositories.position import PositionRepository
        
        repo: IPositionRepository = PositionRepository()
        assert hasattr(repo, 'get_by_symbol')
        assert hasattr(repo, 'get_all')
        assert hasattr(repo, 'upsert')

    def test_trade_repository_protocol(self):
        """Test that TradeRepository implements ITradeRepository."""
        from app.repositories.trade import TradeRepository
        
        repo: ITradeRepository = TradeRepository()
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'get_by_order_id')
        assert hasattr(repo, 'exists')

    def test_settings_repository_protocol(self):
        """Test that SettingsRepository implements ISettingsRepository."""
        from app.repositories.settings import SettingsRepository
        
        repo: ISettingsRepository = SettingsRepository()
        assert hasattr(repo, 'get')
        assert hasattr(repo, 'set')
        assert hasattr(repo, 'get_all')
        assert hasattr(repo, 'get_float')
        assert hasattr(repo, 'get_int')
        assert hasattr(repo, 'get_bool')

