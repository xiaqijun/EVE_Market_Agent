import pytest
from app.tools.cost_calculator import calculate_arbitrage_cost, calculate_vwap


def test_vwap_simple():
    orders = [
        {"price": 5.0, "volume_remain": 100},
        {"price": 6.0, "volume_remain": 100},
    ]
    vwap = calculate_vwap(orders, volume=150)
    assert 5.3 < vwap < 5.7


def test_vwap_partial_fill():
    orders = [
        {"price": 5.0, "volume_remain": 50},
        {"price": 10.0, "volume_remain": 1000},
    ]
    vwap = calculate_vwap(orders, volume=100)
    assert vwap < 8.0


def test_arbitrage_cost_positive_profit():
    cost = calculate_arbitrage_cost(
        buy_price=5.0, sell_price=6.0, volume=1000,
        jumps=5, broker_skill_pct=2.0, sales_tax_pct=1.5
    )
    assert cost["net_profit"] > 0
    assert cost["net_profit_pct"] > 0
    assert "broker_fee" in cost
    assert "sales_tax" in cost
    assert "estimated_shipping" in cost


def test_arbitrage_cost_negative_profit():
    cost = calculate_arbitrage_cost(
        buy_price=5.0, sell_price=5.1, volume=100,
        jumps=30, broker_skill_pct=3.0, sales_tax_pct=3.0
    )
    assert cost["net_profit"] < 0


def test_arbitrage_cost_with_orderbook():
    buy_orders = [{"price": 5.0, "volume_remain": 500}]
    sell_orders = [{"price": 6.0, "volume_remain": 500}]
    cost = calculate_arbitrage_cost(
        buy_price=5.0, sell_price=6.0, volume=500,
        jumps=5, buy_orderbook=buy_orders, sell_orderbook=sell_orders
    )
    assert cost["vwap_buy"] is not None
    assert cost["vwap_sell"] is not None
