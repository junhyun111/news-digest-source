from __future__ import annotations

import logging

from .categories import CATEGORY_ORDER
from .config import Config
from .cch_mmr_recommender import category_ranges_from_quotas
from .filters import normalize_title, normalize_url, select_category_articles
from .naver import fetch_naver_news, parse_naver_response, sample_payload
from .semantic_embeddings import ENHANCED_CATEGORIES, is_semantic_duplicate

LOGGER = logging.getLogger(__name__)
SEMANTIC_BACKFILL_CANDIDATES = 5

QUERY_EXPANSIONS = {
    "ai": ["AI", "\uc778\uacf5\uc9c0\ub2a5", "\uc0dd\uc131\ud615 AI", "AI \ubc18\ub3c4\uccb4", "AI \ubcf4\uc548"],
    "semiconductor": ["semiconductor", "\ubc18\ub3c4\uccb4", "AI \ubc18\ub3c4\uccb4", "HBM", "\uc5d4\ube44\ub514\uc544"],
    "security": ["security", "\ubcf4\uc548", "AI \ubcf4\uc548", "\uc0ac\uc774\ubc84 \ubcf4\uc548", "\uc815\ubcf4\ubcf4\ud638"],
    "\uc778\uacf5\uc9c0\ub2a5": ["\uc778\uacf5\uc9c0\ub2a5", "AI", "\uc0dd\uc131\ud615 AI"],
    "\ubc18\ub3c4\uccb4": ["\ubc18\ub3c4\uccb4", "semiconductor", "HBM", "\uc5d4\ube44\ub514\uc544"],
    "\ubcf4\uc548": ["\ubcf4\uc548", "security", "AI \ubcf4\uc548", "\uc0ac\uc774\ubc84 \ubcf4\uc548"],
}


def expand_queries(queries: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for query in queries:
        candidates = QUERY_EXPANSIONS.get(query.strip().lower(), [query])
        for candidate in candidates:
            key = candidate.strip().lower()
            if key and key not in seen:
                seen.add(key)
                expanded.append(candidate.strip())
    return expanded


def iter_seed_queries(config: Config) -> list[tuple[str, str]]:
    seeded_queries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for category in CATEGORY_ORDER:
        for query in config.category_queries.get(category, []):
            normalized_query = query.strip()
            key = (category, normalized_query.casefold())
            if normalized_query and key not in seen:
                seen.add(key)
                seeded_queries.append((category, normalized_query))
    return seeded_queries


def iter_category_queries(config: Config, category: str) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for query in config.category_queries.get(category, []):
        normalized_query = query.strip()
        key = normalized_query.casefold()
        if normalized_query and key not in seen:
            seen.add(key)
            queries.append(normalized_query)
    return queries


def collect_articles(config: Config):
    articles = []
    if config.use_sample_data:
        LOGGER.info("Using sample news data")
        return parse_naver_response(sample_payload(config.timezone), query="sample", timezone=config.timezone)

    for seed_category, query in iter_seed_queries(config):
        LOGGER.info("Fetching Naver news for seed_category=%s query=%s", seed_category, query)
        payload = fetch_naver_news(config.naver_client_id, config.naver_client_secret, query)
        articles.extend(
            parse_naver_response(
                payload,
                query=query,
                timezone=config.timezone,
                seed_category=seed_category,
            )
        )
    return articles


def collect_category_articles(config: Config, category: str):
    """한 카테고리의 검색어를 순회하며 네이버 뉴스 결과를 수집합니다."""
    articles = []
    if config.use_sample_data:
        LOGGER.info("Using sample news data for category=%s", category)
        return parse_naver_response(
            sample_payload(config.timezone),
            query="sample",
            timezone=config.timezone,
            seed_category=category,
        )

    for query in iter_category_queries(config, category):
        LOGGER.info("Fetching Naver news for category=%s query=%s", category, query)
        payload = fetch_naver_news(config.naver_client_id, config.naver_client_secret, query)
        articles.extend(
            parse_naver_response(
                payload,
                query=query,
                timezone=config.timezone,
                seed_category=category,
            )
        )
    return articles


def build_digest(config: Config):
    """전체 뉴스 리스트를 만듭니다.

    흐름: 카테고리별 수집 -> 카테고리별 추천 -> 전체 중복 제거 -> 발송 이력 제외.
    """
    selected = []
    total_collected = 0
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    category_ranges = category_ranges_from_quotas(config.category_quotas)

    for category in CATEGORY_ORDER:
        remaining_slots = config.max_articles - len(selected)
        if remaining_slots <= 0:
            break

        _, category_max = category_ranges.get(category, (0, 0))
        category_max = min(category_max, remaining_slots)
        if category_max <= 0:
            continue

        # 카테고리마다 검색과 추천을 따로 수행해야 quota와 필수 조건이 섞이지 않습니다.
        articles = collect_category_articles(config, category)
        total_collected += len(articles)
        selection_limit = category_max
        if category in ENHANCED_CATEGORIES:
            selection_limit = min(len(articles), category_max + SEMANTIC_BACKFILL_CANDIDATES)
        category_selected = select_category_articles(
            articles,
            category=category,
            keyword_weights=config.keyword_weights,
            min_score=config.min_score,
            max_articles=selection_limit,
            timezone=config.timezone,
            recommendation_weights=config.recommendation_weights,
            category_quotas={category: selection_limit},
            mmr_lambda=config.mmr_lambda,
        )

        # 카테고리 간 URL·제목 중복과 임베딩 의미 중복을 제거합니다.
        accepted_in_category = 0
        for article in category_selected:
            if accepted_in_category >= category_max:
                break
            url_key = normalize_url(article.canonical_url)
            title_key = normalize_title(article.title)
            if url_key in seen_urls or title_key in seen_titles:
                continue
            if category in ENHANCED_CATEGORIES and any(
                existing.category in ENHANCED_CATEGORIES
                and is_semantic_duplicate(article, existing)
                for existing in selected
            ):
                continue
            seen_urls.add(url_key)
            seen_titles.add(title_key)
            selected.append(article)
            accepted_in_category += 1

    LOGGER.info("Collected %s articles, selected %s articles", total_collected, len(selected))
    return selected
