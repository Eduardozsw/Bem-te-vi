from dataclasses import dataclass, field


@dataclass
class RunStatus:
    warnings: list[str] = field(default_factory=list)
    batches_total: int = 0
    batches_failed: int = 0

    def add(self, message: str) -> None:
        self.warnings.append(message)
