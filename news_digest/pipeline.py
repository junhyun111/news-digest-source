from __future__ import annotations

import logging
from typing import Callable

from .categories import CATEGORY_INDUSTRY, CATEGORY_ORDER
from .config import Config
from .cch_mmr_recommender import category_ranges_from_quotas
from .filters import select_category_articles
from .naver import fetch_naver_news, parse_naver_response, sample_payload
from .normalization import normalize_title, normalize_url
from .semantic_embeddings import ENHANCED_CATEGORIES, is_semantic_duplicate

LOGGER = logging.getLogger(__name__)
SEMANTIC_BACKFILL_CANDIDATES = 5

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


def build_digest(
    config: Config,
    diagnostic_sink: Callable[[dict[str, object]], None] | None = None,
):
    """전체 뉴스 리스트를 만듭니다.

    흐름: 카테고리별 수집 -> 카테고리별 추천 -> 전체 중복 제거 -> 발송 이력 제외.
    """
    selected = []
    total_collected = 0
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    category_ranges = category_ranges_from_quotas(config.category_quotas)

    for category in CATEGORY_ORDER:
        _, category_max = category_ranges.get(category, (0, 0))
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
            diagnostic_sink=diagnostic_sink if category == CATEGORY_INDUSTRY else None,
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

    if len(selected) > config.max_articles:
        ranked_indices = sorted(
            range(len(selected)),
            key=lambda index: (-selected[index].score, index),
        )[: config.max_articles]
        keep_indices = set(ranked_indices)
        selected = [article for index, article in enumerate(selected) if index in keep_indices]

    LOGGER.info("Collected %s articles, selected %s articles", total_collected, len(selected))
    return selected
