def calculate_vwap(orders: list[dict], volume: int) -> float:
    total_cost = 0.0
    remaining = volume
    for order in sorted(orders, key=lambda o: o["price"]):
        fill = min(order["volume_remain"], remaining)
        total_cost += fill * order["price"]
        remaining -= fill
        if remaining <= 0:
            break
    filled = volume - remaining
    return total_cost / filled if filled > 0 else 0.0


def calculate_arbitrage_cost(
    buy_price: float,
    sell_price: float,
    volume: int,
    jumps: int = 5,
    broker_skill_pct: float = 2.0,
    sales_tax_pct: float = 1.5,
    buy_orderbook: list[dict] | None = None,
    sell_orderbook: list[dict] | None = None,
    shipping_per_jump: float = 50000.0,
    daily_capital_cost_pct: float = 0.02,
    estimated_hold_days: int = 3,
) -> dict:
    effective_buy = calculate_vwap(buy_orderbook, volume) if buy_orderbook else buy_price
    effective_sell = calculate_vwap(sell_orderbook, volume) if sell_orderbook else sell_price

    raw_spread = effective_sell - effective_buy
    raw_spread_pct = (raw_spread / effective_buy) * 100 if effective_buy > 0 else 0

    buy_total = effective_buy * volume
    sell_total = effective_sell * volume
    gross_profit = sell_total - buy_total

    broker_fee = buy_total * (broker_skill_pct / 100)
    tax = sell_total * (sales_tax_pct / 100)
    estimated_shipping = jumps * shipping_per_jump
    capital_cost = buy_total * (daily_capital_cost_pct / 100) * estimated_hold_days

    total_costs = broker_fee + tax + estimated_shipping + capital_cost
    net_profit = gross_profit - total_costs
    net_profit_pct = (net_profit / buy_total) * 100 if buy_total > 0 else 0

    return {
        "effective_buy_price": round(effective_buy, 2),
        "effective_sell_price": round(effective_sell, 2),
        "raw_spread_pct": round(raw_spread_pct, 2),
        "gross_profit": round(gross_profit, 2),
        "broker_fee": round(broker_fee, 2),
        "sales_tax": round(tax, 2),
        "estimated_shipping": round(estimated_shipping, 2),
        "capital_cost": round(capital_cost, 2),
        "total_costs": round(total_costs, 2),
        "net_profit": round(net_profit, 2),
        "net_profit_pct": round(net_profit_pct, 2),
        "vwap_buy": round(effective_buy, 2) if buy_orderbook else None,
        "vwap_sell": round(effective_sell, 2) if sell_orderbook else None,
    }
