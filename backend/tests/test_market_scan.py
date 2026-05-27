import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from app.tasks.market_scan import _store_orders, _async_cleanup
from app.models.market import MarketOrder


@pytest.mark.asyncio
async def test_store_orders_inserts_orders():
    """Store orders from ESI response into database."""
    mock_db = AsyncMock()
    orders = [
        {
            "type_id": 34, "location_id": 60003760, "region_id": 10000002,
            "system_id": 30000142, "order_id": 12345, "is_buy_order": False,
            "price": 5.5, "volume_remain": 1000, "volume_total": 5000,
            "issued": "2026-05-20T10:00:00Z", "duration": 90, "range": "region",
        },
        {
            "type_id": 35, "location_id": 60003760, "region_id": 10000002,
            "system_id": 30000142, "order_id": 12346, "is_buy_order": True,
            "price": 4.8, "volume_remain": 2000, "volume_total": 2000,
            "issued": "2026-05-20T10:00:00Z", "duration": 30, "range": "station",
        },
    ]
    await _store_orders(mock_db, orders)
    assert mock_db.add.call_count == 2
    added = [c.args[0] for c in mock_db.add.call_args_list]
    assert all(isinstance(o, MarketOrder) for o in added)
    assert added[0].type_id == 34
    assert added[1].type_id == 35


@pytest.mark.asyncio
async def test_store_orders_handles_empty_list():
    """Empty order list should not crash."""
    mock_db = AsyncMock()
    await _store_orders(mock_db, [])
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_store_orders_sets_fetched_at():
    """All orders should have the same fetched_at timestamp."""
    mock_db = AsyncMock()
    orders = [
        {"type_id": 34, "order_id": 1, "is_buy_order": False, "price": 5.0,
         "volume_remain": 100, "volume_total": 100, "duration": 30},
        {"type_id": 35, "order_id": 2, "is_buy_order": True, "price": 4.0,
         "volume_remain": 200, "volume_total": 200, "duration": 30},
    ]
    await _store_orders(mock_db, orders)
    added = [c.args[0] for c in mock_db.add.call_args_list]
    assert added[0].fetched_at == added[1].fetched_at
    assert isinstance(added[0].fetched_at, datetime)


@pytest.mark.asyncio
async def test_store_orders_defaults_missing_fields():
    """Orders with missing optional fields should use defaults."""
    mock_db = AsyncMock()
    orders = [
        {"type_id": 34, "order_id": 99, "is_buy_order": False,
         "price": 10.0, "volume_remain": 50, "volume_total": 50, "duration": 30},
    ]
    await _store_orders(mock_db, orders)
    added = mock_db.add.call_args_list[0].args[0]
    assert added.station_id == 0
    assert added.region_id == 0
    assert added.system_id == 0
    assert added.range == "station"


@pytest.mark.asyncio
async def test_store_orders_handles_duplicate_order_ids():
    """Duplicate order_ids in same batch should update existing, not crash."""
    mock_db = AsyncMock()
    orders = [
        {"type_id": 34, "order_id": 100, "is_buy_order": False, "price": 5.0,
         "volume_remain": 100, "volume_total": 500, "duration": 30},
        {"type_id": 34, "order_id": 100, "is_buy_order": False, "price": 5.0,
         "volume_remain": 50, "volume_total": 500, "duration": 30},
    ]
    await _store_orders(mock_db, orders)
    assert mock_db.add.call_count == 2


@pytest.mark.asyncio
async def test_store_orders_maps_esi_fields_correctly():
    """ESI uses location_id not station_id."""
    mock_db = AsyncMock()
    orders = [
        {"type_id": 34, "location_id": 60003760, "region_id": 10000002,
         "system_id": 30000142, "order_id": 1, "is_buy_order": False,
         "price": 5.0, "volume_remain": 100, "volume_total": 500,
         "duration": 30, "range": "region"},
    ]
    await _store_orders(mock_db, orders)
    added = mock_db.add.call_args_list[0].args[0]
    assert added.station_id == 60003760
    assert added.region_id == 10000002
    assert added.system_id == 30000142
    assert added.range == "region"


@pytest.mark.asyncio
async def test_store_orders_does_not_commit():
    """_store_orders should not commit — caller is responsible."""
    mock_db = AsyncMock()
    orders = [
        {"type_id": 34, "order_id": 1, "is_buy_order": False, "price": 5.0,
         "volume_remain": 100, "volume_total": 100, "duration": 30},
    ]
    await _store_orders(mock_db, orders)
    mock_db.commit.assert_not_called()


def test_scan_task_disposes_engine_before_running():
    """Celery tasks must dispose the SQLAlchemy engine after fork to reset connection pool."""
    import inspect
    from app.tasks.market_scan import scan_region_market
    source = inspect.getsource(scan_region_market)
    assert "engine.dispose" in source, (
        "scan_region_market must call engine.dispose() before running async work. "
        "Celery forks workers and SQLAlchemy connections don't survive forks."
    )


def test_cleanup_task_disposes_engine_before_running():
    """Cleanup task also needs engine.dispose() after Celery fork."""
    import inspect
    from app.tasks.market_scan import cleanup_old_orders
    source = inspect.getsource(cleanup_old_orders)
    assert "engine.dispose" in source, (
        "cleanup_old_orders must call engine.dispose() before running async work."
    )
