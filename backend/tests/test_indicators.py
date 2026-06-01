import pytest
from app.tools.indicators import calc_sma, calc_ema, calc_rsi, calc_volatility, calc_volume_trend


def test_sma_basic():
    prices = [10, 12, 14, 16, 18]
    result = calc_sma(prices, window=3)
    assert len(result) == 3
    assert result[0] == pytest.approx(12.0)


def test_sma_insufficient_data():
    result = calc_sma([10], window=5)
    assert result == []


def test_ema_weighted():
    prices = [10, 10, 10, 20]
    result = calc_ema(prices, window=3)
    assert result[-1] > 10


def test_rsi_range():
    prices = [10, 11, 12, 11, 10, 9, 10, 11, 12, 13, 14, 15, 14, 13, 12]
    result = calc_rsi(prices, period=14)
    assert 0 <= result <= 100


def test_rsi_uptrend():
    up_prices = list(range(10, 30))
    result = calc_rsi(up_prices, period=14)
    assert result > 50


def test_rsi_insufficient_data():
    result = calc_rsi([10, 12], period=14)
    assert result == 50.0


def test_volatility_positive():
    prices = [10, 12, 10, 12, 10, 12]
    result = calc_volatility(prices, window=5)
    assert result > 0


def test_volume_trend_up():
    volumes = [100, 100, 100, 100, 100, 300, 300, 300, 300, 300]
    result = calc_volume_trend(volumes, window=3)
    assert result == "up"


def test_volume_trend_insufficient():
    result = calc_volume_trend([100], window=7)
    assert result == "insufficient_data"


@pytest.mark.asyncio
async def test_fetch_indicators_returns_dict():
    """fetch_indicators should return a dict with indicator keys."""
    from app.tools.indicators import fetch_indicators
    from unittest.mock import AsyncMock, MagicMock
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[])
    mock_db.execute = AsyncMock(return_value=mock_result)
    result = await fetch_indicators(mock_db, type_id=34)
    assert isinstance(result, dict)
    assert "sma_30" in result
    assert "rsi_14" in result
    assert "data_points" in result
