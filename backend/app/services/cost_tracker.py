import time
from collections import defaultdict
from app.config import settings


class CostTracker:
    def __init__(self, monthly_budget: float = 50.0):
        self.budget = monthly_budget
        self.usage: dict[str, float] = defaultdict(float)
        self._reset_time = time.time()

    def record(self, alias: str, input_tokens: int, output_tokens: int):
        config = settings.load_model_config()
        aliases = config.get("aliases", {})
        model_info = aliases.get(alias, {})
        model = model_info.get("model", alias)

        pricing = {
            "claude-opus-4-20250514": (15.0, 75.0),
            "claude-sonnet-4-20250514": (3.0, 15.0),
            "claude-haiku-4-5-20251001": (0.80, 4.0),
            "gpt-4o-mini": (0.15, 0.60),
            "deepseek-chat": (0.14, 0.28),
        }
        input_price, output_price = pricing.get(model, (1.0, 5.0))
        cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
        self.usage[alias] += cost

    def total_cost(self) -> float:
        return sum(self.usage.values())

    def budget_remaining(self) -> float:
        return self.budget - self.total_cost()

    def is_over_budget(self) -> bool:
        return self.total_cost() >= self.budget

    def is_warning(self) -> bool:
        return self.total_cost() >= self.budget * 0.8


cost_tracker = CostTracker(settings.llm_monthly_budget_usd)
