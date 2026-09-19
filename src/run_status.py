from dataclasses import dataclass, field


@dataclass
class RunStatus:
    warnings: list[str] = field(default_factory=list)
    batches_total: int = 0
    batches_failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    cost_unknown: bool = False  # alguma chamada sem preço conhecido → custo total não é confiável

    def add(self, message: str) -> None:
        self.warnings.append(message)

    def record_usage(self, prompt: int, completion: int, cost: float | None) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        if cost is None:
            self.cost_unknown = True
        else:
            self.cost_usd += cost

    @property
    def total_cost_usd(self) -> float | None:
        return None if self.cost_unknown else self.cost_usd
