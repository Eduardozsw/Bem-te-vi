from dataclasses import dataclass, field


@dataclass
class RunStatus:
    warnings: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.warnings.append(message)
