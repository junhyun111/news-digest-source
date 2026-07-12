from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Article:
    title: str
    description: str
    originallink: str
    link: str
    pub_date: datetime
    query: str = ""
    seed_category: str = ""
    score: float = 0.0
    category: str = ""
    reason: str = ""

    @property
    def canonical_url(self) -> str:
        return self.originallink or self.link
