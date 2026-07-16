from __future__ import annotations

from .keyword_matching import keyword_matches_text
from .models import Article


def score_article(article: Article, keyword_weights: dict[str, float]) -> float:
    """CCH-MMR이 결과를 내지 못할 때 쓰는 단순 키워드 점수입니다."""
    title = article.title.lower()
    description = article.description.lower()
    score = 0.0

    for keyword, weight in keyword_weights.items():
        needle = keyword.lower()
        is_compound = len(needle.split()) > 1
        title_hits = 1 if is_compound and keyword_matches_text(title, needle) else title.count(needle)
        description_hits = (
            1 if is_compound and keyword_matches_text(description, needle) else description.count(needle)
        )
        if title_hits:
            # 제목은 기사 주제를 압축하므로 본문보다 3배 강하게 봅니다.
            score += title_hits * weight * 3.0
        if description_hits:
            score += description_hits * weight

    if article.query and keyword_matches_text(title, article.query):
        score += 2.0
    if article.query and keyword_matches_text(description, article.query):
        score += 1.0
    if len(article.description) >= 40:
        score += 0.5
    return round(score, 2)
