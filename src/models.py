from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    source: str
    title: str
    content: str
    url: str
    published_at: datetime
    sources: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    title: str
    source: str
    url: str
    relevance: int
    summary: str
    why_it_matters: str
    impacts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
