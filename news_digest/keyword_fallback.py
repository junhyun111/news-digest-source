from __future__ import annotations

from .models import Article


def score_article(article: Article, keyword_weights: dict[str, float]) -> float:
    """CCH-MMR이 결과를 내지 못할 때 쓰는 단순 키워드 점수입니다."""
    title = article.title.lower()
    description = article.description.lower()
    score = 0.0

    for keyword, weight in keyword_weights.items():
        needle = keyword.lower()
        title_hits = title.count(needle)
        description_hits = description.count(needle)
        if title_hits:
            # 제목은 기사 주제를 압축하므로 본문보다 3배 강하게 봅니다.
            score += title_hits * weight * 3.0
        if description_hits:
            score += description_hits * weight

    if article.query and article.query.lower() in title:
        score += 2.0
    if article.query and article.query.lower() in description:
        score += 1.0
    if len(article.description) >= 40:
        score += 0.5
    return round(score, 2)
