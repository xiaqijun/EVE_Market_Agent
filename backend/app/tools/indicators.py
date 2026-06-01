import math


def calc_sma(prices: list[float], window: int = 20) -> list[float]:
    if len(prices) < window:
        return []
    return [sum(prices[i:i + window]) / window for i in range(len(prices) - window + 1)]


def calc_ema(prices: list[float], window: int = 20) -> list[float]:
    if len(prices) < window:
        return []
    multiplier = 2 / (window + 1)
    ema = [sum(prices[:window]) / window]
    for price in prices[window:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def calc_rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_volatility(prices: list[float], window: int = 20) -> float:
    if len(prices) < window:
        return 0.0
    recent = prices[-window:]
    mean = sum(recent) / len(recent)
    variance = sum((p - mean) ** 2 for p in recent) / len(recent)
    return math.sqrt(variance) / mean if mean != 0 else 0.0


def calc_volume_trend(volumes: list[int], window: int = 7) -> str:
    if len(volumes) < window * 2:
        return "insufficient_data"
    recent_avg = sum(volumes[-window:]) / window
    prior_avg = sum(volumes[-window * 2:-window]) / window
    if recent_avg > prior_avg * 1.2:
        return "up"
    elif recent_avg < prior_avg * 0.8:
        return "down"
    return "flat"


async def fetch_indicators(db, type_id: int, region_id: int = 10000002) -> dict:
    """Fetch 30-day price history from DB and compute technical indicators.

    Returns dict with keys: sma_30, ema_15, rsi_14, volatility_30d, volume_trend, prices, volumes, data_points.
    Returns empty values if insufficient data.
    """
    from sqlalchemy import text
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        text("SELECT average, volume, date FROM market_history "
             "WHERE type_id = :type_id AND region_id = :region_id AND date >= :cutoff "
             "ORDER BY date ASC"),
        {"type_id": type_id, "region_id": region_id, "cutoff": cutoff},
    )
    rows = result.fetchall()

    if not rows:
        return {
            "sma_30": None, "ema_15": None, "rsi_14": None,
            "volatility_30d": None, "volume_trend": "insufficient_data",
            "prices": [], "volumes": [], "data_points": 0,
        }

    prices = [float(r[0]) for r in rows if r[0]]
    volumes = [int(r[1]) for r in rows if r[1]]

    if len(prices) < 2:
        return {
            "sma_30": None, "ema_15": None, "rsi_14": None,
            "volatility_30d": None, "volume_trend": "insufficient_data",
            "prices": prices, "volumes": volumes, "data_points": len(prices),
        }

    sma_vals = calc_sma(prices, min(30, len(prices)))
    ema_vals = calc_ema(prices, min(15, len(prices)))

    return {
        "sma_30": round(sma_vals[-1], 2) if sma_vals else None,
        "ema_15": round(ema_vals[-1], 2) if ema_vals else None,
        "rsi_14": round(calc_rsi(prices, min(14, len(prices) - 1)), 1),
        "volatility_30d": round(calc_volatility(prices, min(20, len(prices))), 4),
        "volume_trend": calc_volume_trend(volumes, min(7, len(volumes))),
        "prices": prices,
        "volumes": volumes,
        "data_points": len(prices),
    }
