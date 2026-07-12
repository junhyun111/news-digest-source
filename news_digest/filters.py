from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .categories import classify_article
from .cch_mmr_recommender import select_cch_mmr_articles
from .keyword_fallback import score_article
from .models import Article
from .timezones import get_timezone


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def normalize_url(url: str) -> str:
    split = urlsplit(url.strip())
    query = urlencode(
        [(key, value) for key, value in parse_qsl(split.query, keep_blank_values=True) if key not in TRACKING_PARAMS]
    )
    path = split.path.rstrip("/") or split.path
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, query, ""))


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def yesterday_range(now: datetime | None = None, timezone: str = "Asia/Seoul") -> tuple[datetime, datetime]:
    tz = get_timezone(timezone)
    localized_now = (now or datetime.now(tz)).astimezone(tz)
    yesterday = localized_now.date() - timedelta(days=1)
    start = datetime.combine(yesterday, datetime.min.time(), tz)
    end = start + timedelta(days=1)
    return start, end


def is_from_yesterday(article: Article, now: datetime | None = None, timezone: str = "Asia/Seoul") -> bool:
    start, end = yesterday_range(now=now, timezone=timezone)
    pub_date = article.pub_date.astimezone(get_timezone(timezone))
    return start <= pub_date < end


def recommendation_range(now: datetime | None = None, timezone: str = "Asia/Seoul") -> tuple[datetime, datetime]:
    tz = get_timezone(timezone)
    localized_now = (now or datetime.now(tz)).astimezone(tz)
    start_days_back = 3 if localized_now.weekday() == 0 else 1
    start_date = localized_now.date() - timedelta(days=start_days_back)
    start = datetime.combine(start_date, datetime.min.time(), tz)
    end = datetime.combine(localized_now.date(), datetime.min.time(), tz) + timedelta(hours=7)
    return start, end


def is_in_recommendation_range(article: Article, now: datetime | None = None, timezone: str = "Asia/Seoul") -> bool:
    start, end = recommendation_range(now=now, timezone=timezone)
    pub_date = article.pub_date.astimezone(get_timezone(timezone))
    return start <= pub_date < end


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        url_key = normalize_url(article.canonical_url)
        title_key = normalize_title(article.title)
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(article)
    return unique


def select_keyword_fallback_articles(
    articles: list[Article],
    keyword_weights: dict[str, float],
    min_score: float,
    max_articles: int,
    category: str | None = None,
) -> list[Article]:
    """CCH-MMR 결과가 없을 때 사용하는 단순 키워드 기반 보충 선택입니다."""
    fallback_articles = [
        replace(
            article,
            score=score_article(article, keyword_weights),
            category=category or classify_article(article),
        )
        for article in articles
    ]
    relevant_fallback_articles = [article for article in fallback_articles if article.score >= min_score]

    unique_articles = deduplicate_articles(relevant_fallback_articles)
    return sorted(unique_articles, key=lambda article: (-article.score, article.pub_date))[:max_articles]


def select_articles(
    articles: list[Article],
    keyword_weights: dict[str, float],
    min_score: float,
    max_articles: int,
    timezone: str = "Asia/Seoul",
    now: datetime | None = None,
    recommendation_weights: dict[str, float] | None = None,
    category_quotas: dict[str, int] | None = None,
    mmr_lambda: float = 0.70,
) -> list[Article]:
    recommendation_articles = [
        article for article in articles if is_in_recommendation_range(article, now=now, timezone=timezone)
    ]
    selected = select_cch_mmr_articles(
        recommendation_articles,
        min_score=min_score,
        max_articles=max_articles,
        timezone=timezone,
        now=now,
        weights=recommendation_weights,
        category_quotas=category_quotas,
        lambda_value=mmr_lambda,
    )
    if selected:
        return selected

    return select_keyword_fallback_articles(recommendation_articles, keyword_weights, min_score, max_articles)


def select_category_articles(
    articles: list[Article],
    category: str,
    keyword_weights: dict[str, float],
    min_score: float,
    max_articles: int,
    timezone: str = "Asia/Seoul",
    now: datetime | None = None,
    recommendation_weights: dict[str, float] | None = None,
    category_quotas: dict[str, int] | None = None,
    mmr_lambda: float = 0.70,
) -> list[Article]:
    recommendation_articles = [
        article for article in articles if is_in_recommendation_range(article, now=now, timezone=timezone)
    ]
    selected = select_cch_mmr_articles(
        recommendation_articles,
        min_score=min_score,
        max_articles=max_articles,
        timezone=timezone,
        now=now,
        weights=recommendation_weights,
        category_quotas=category_quotas,
        lambda_value=mmr_lambda,
        target_categories=[category],
    )
    if selected:
        return selected

    return select_keyword_fallback_articles(
        recommendation_articles,
        keyword_weights,
        min_score,
        max_articles,
        category=category,
    )
