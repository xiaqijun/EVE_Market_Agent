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
