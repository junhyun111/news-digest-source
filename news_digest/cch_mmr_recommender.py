from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from math import exp
import logging
import os
import re
from typing import Iterable

from . import settings
from .categories import (
    CATEGORY_GOVERNMENT,
    CATEGORY_INDUSTRY,
    CATEGORY_INNODEP,
    CATEGORY_ORDER,
    CATEGORY_SECURITY,
    CATEGORY_VENTURE,
    source_name,
)
from .models import Article
from .normalization import normalize_url
from .recommendation_rules import (
    DEFAULT_WEIGHTS,
    SEED_CATEGORY_BONUS,
    SEMANTIC_RELEVANCE_BLEND,
    SEMANTIC_REDUNDANCY_BLEND,
    SEMANTIC_COSINE_FLOOR,
    QUALITY_SCORE_WINDOW,
    QUALITY_SCORE_CLIFF,
    MMR_MIN_SELECTION_SCORE,
    DEFAULT_CATEGORY_RANGES,
    DEFAULT_GLOBAL_TITLE_WEIGHTS,
    DEFAULT_CATEGORY_TITLE_WEIGHTS,
    CATEGORY_TITLE_ENV_NAMES,
    DEFAULT_NEGATIVE_TITLE_WEIGHTS,
    CATEGORY_KEYWORDS,
    BLACKLIST_KEYWORDS,
    INNODEP_ENTITIES,
    INNODEP_NEGATIVE_KEYWORDS,
    SECURITY_CORE_KEYWORDS,
    SECURITY_TITLE_CORE_KEYWORDS,
    SECURITY_CYBER_ONLY_KEYWORDS,
    GENERAL_DISASTER_KEYWORDS,
    GOVERNMENT_ACTORS,
    GOVERNMENT_ACTIONS,
    COMPANY_REGISTRATION_PATTERNS,
    COMPANY_GOVERNMENT_PR_KEYWORDS,
    COMPANY_GOVERNMENT_BUSINESS_KEYWORDS,
    ADDITIONAL_CATEGORY_KEYWORDS,
    GOVERNMENT_ACTOR_ALIASES,
    GOVERNMENT_ACTION_ALIASES,
    GOVERNMENT_GENERAL_NOISE_KEYWORDS,
    VENTURE_CORE_KEYWORDS,
    VENTURE_WEAK_KEYWORDS,
    VENTURE_NOISE_KEYWORDS,
    INDUSTRY_STRONG_TOPIC_KEYWORDS,
    INDUSTRY_GENERIC_TECH_KEYWORDS,
    INDUSTRY_BUSINESS_ACTION_KEYWORDS,
    INDUSTRY_NOISE_KEYWORDS,
    GOVERNMENT_NOISE_ALLOWED_TOPICS,
    GOVERNMENT_PUBLIC_ACTOR_KEYWORDS,
    GOVERNMENT_PRIMARY_KEYWORDS,
    GOVERNMENT_SECONDARY_KEYWORDS,
    GOVERNMENT_COMPANY_RELEVANT_KEYWORDS,
    GOVERNMENT_PROGRAM_KEYWORDS,
    GOVERNMENT_TECH_POLICY_KEYWORDS,
    GOVERNMENT_EXCLUDE_KEYWORDS,
    GOVERNMENT_NORMAL_ACTION_KEYWORDS,
    INDUSTRY_COMPANY_ALIASES,
    SOURCE_SCORES,
    IMPORTANT_ENTITIES,
)
from .semantic_embeddings import (
    ENHANCED_CATEGORIES,
    is_semantic_duplicate,
    prepare_semantic_articles,
    semantic_category_score,
    semantic_similarity,
)
from .text_similarity import lexical_cosine, title_similarity
from .timezones import get_timezone

LOGGER = logging.getLogger(__name__)


def article_text(article: Article) -> str:
    return f"{article.title} {article.description}".strip()


def contains_innodep(article: Article) -> bool:
    text = article_text(article).casefold()
    return any(entity.casefold() in text for entity in INNODEP_ENTITIES)


def has_innodep_title(article: Article) -> bool:
    title = article.title.casefold()
    return any(entity.casefold() in title for entity in INNODEP_ENTITIES)


def is_blacklisted_article(article: Article) -> bool:
    text = article_text(article).casefold()
    return any(keyword.casefold() in text for keyword in BLACKLIST_KEYWORDS)


def is_negative_innodep_article(article: Article) -> bool:
    if not contains_innodep(article):
        return False
    text = article_text(article).casefold()
    return any(keyword.casefold() in text for keyword in INNODEP_NEGATIVE_KEYWORDS)


def has_any_keyword(article: Article, keywords: list[str]) -> bool:
    text = article_text(article).casefold()
    return any(keyword.casefold() in text for keyword in keywords)


def text_has_any_keyword(text: str, keywords: list[str]) -> bool:
    folded = text.casefold()
    return any(keyword.casefold() in folded for keyword in keywords)


def category_keywords(category: str) -> list[str]:
    return CATEGORY_KEYWORDS[category] + ADDITIONAL_CATEGORY_KEYWORDS.get(category, [])


def parse_weight_pairs(raw: str) -> dict[str, float]:
    """Parse comma-separated keyword:weight pairs from .env values."""
    weights: dict[str, float] = {}
    if not raw:
        return weights

    for item in raw.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue

        keyword, weight = item.rsplit(":", 1)
        keyword = keyword.strip()
        if not keyword:
            continue

        try:
            weights[keyword] = float(weight.strip())
        except ValueError:
            LOGGER.warning("Invalid keyword weight ignored: %s", item)

    return weights


def category_title_weights(category: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    weights.update(DEFAULT_GLOBAL_TITLE_WEIGHTS)
    weights.update(DEFAULT_CATEGORY_TITLE_WEIGHTS.get(category, {}))
    weights.update(settings.TITLE_KEYWORD_WEIGHTS)
    weights.update(settings.CATEGORY_TITLE_WEIGHTS.get(category, {}))
    weights.update(parse_weight_pairs(os.getenv("TITLE_KEYWORD_WEIGHTS", "")))

    env_name = CATEGORY_TITLE_ENV_NAMES.get(category)
    if env_name:
        weights.update(parse_weight_pairs(os.getenv(env_name, "")))

    return weights


def negative_title_weights() -> dict[str, float]:
    weights = dict(DEFAULT_NEGATIVE_TITLE_WEIGHTS)
    weights.update(settings.NEGATIVE_TITLE_WEIGHTS)
    weights.update(parse_weight_pairs(os.getenv("NEGATIVE_TITLE_WEIGHTS", "")))
    return weights


def is_security_noise(article: Article) -> bool:
    title = article.title.casefold()
    text = article_text(article)
    has_video_security_core = text_has_any_keyword(text, SECURITY_CORE_KEYWORDS)
    if text_has_any_keyword(text, SECURITY_CYBER_ONLY_KEYWORDS) and not has_video_security_core:
        return True
    title_has_disaster = any(keyword.casefold() in title for keyword in GENERAL_DISASTER_KEYWORDS)
    title_has_security_core = any(keyword.casefold() in title for keyword in SECURITY_CORE_KEYWORDS)
    if title_has_disaster and not title_has_security_core:
        return True
    if has_video_security_core:
        return False
    return has_any_keyword(article, GENERAL_DISASTER_KEYWORDS)


def has_security_core_content(article: Article) -> bool:
    return text_has_any_keyword(article_text(article), SECURITY_CORE_KEYWORDS)


def has_security_core_title(article: Article) -> bool:
    return text_has_any_keyword(article.title, SECURITY_TITLE_CORE_KEYWORDS)


def is_government_led_article(article: Article) -> bool:
    text = article_text(article).casefold()
    title = article.title.casefold()
    first_clause = re.split(r"[,，·…]", title, maxsplit=1)[0]
    has_actor = any(
        first_clause.startswith(actor.casefold()) or actor.casefold() in first_clause
        for actor in GOVERNMENT_ACTORS + GOVERNMENT_ACTOR_ALIASES
    )
    has_action = any(action.casefold() in text for action in GOVERNMENT_ACTIONS + GOVERNMENT_ACTION_ALIASES)
    return has_actor and has_action


def is_company_registration_article(article: Article) -> bool:
    return has_any_keyword(article, COMPANY_REGISTRATION_PATTERNS)


def is_private_company_government_pr_article(article: Article) -> bool:
    """민간 기업이 정부기관 인증/수상/지정 등을 받았다는 PR성 기사는 제외합니다."""
    if is_government_led_article(article):
        return False
    text = article_text(article)
    if not text_has_any_keyword(text, GOVERNMENT_ACTOR_ALIASES + GOVERNMENT_ACTORS):
        return False
    return text_has_any_keyword(text, COMPANY_GOVERNMENT_PR_KEYWORDS)


def is_private_company_government_business_article(article: Article) -> bool:
    """민간 기업이 정부 사업을 수주·낙찰·공급했다는 기업 성과 기사를 제외합니다."""
    if is_government_led_article(article):
        return False
    text = article_text(article)
    if not text_has_any_keyword(text, GOVERNMENT_ACTOR_ALIASES + GOVERNMENT_ACTORS):
        return False
    return text_has_any_keyword(article.title, COMPANY_GOVERNMENT_BUSINESS_KEYWORDS)


def is_general_government_noise(article: Article) -> bool:
    if not has_any_keyword(article, GOVERNMENT_GENERAL_NOISE_KEYWORDS):
        return False
    return not text_has_any_keyword(article.title, GOVERNMENT_NOISE_ALLOWED_TOPICS)


def has_government_actor(article: Article) -> bool:
    title = article.title.casefold()
    text = article_text(article).casefold()
    if any(actor.casefold() in title for actor in GOVERNMENT_ACTOR_ALIASES):
        return True
    concrete_actors = [keyword for keyword in GOVERNMENT_PUBLIC_ACTOR_KEYWORDS if keyword != "공공"]
    if any(actor.casefold() in title for actor in concrete_actors):
        return True
    return "장관" in text and any(keyword.casefold() in title for keyword in GOVERNMENT_TECH_POLICY_KEYWORDS)


def has_government_priority_domain(article: Article) -> bool:
    text = article_text(article)
    has_tech = text_has_any_keyword(text, GOVERNMENT_TECH_POLICY_KEYWORDS)
    has_program = text_has_any_keyword(text, GOVERNMENT_PROGRAM_KEYWORDS)
    has_primary = text_has_any_keyword(text, GOVERNMENT_PRIMARY_KEYWORDS)
    has_secondary = text_has_any_keyword(text, GOVERNMENT_SECONDARY_KEYWORDS)
    has_company_relevant = text_has_any_keyword(text, GOVERNMENT_COMPANY_RELEVANT_KEYWORDS)
    has_action = text_has_any_keyword(text, GOVERNMENT_ACTION_ALIASES + GOVERNMENT_NORMAL_ACTION_KEYWORDS)
    return (
        (has_tech and (has_program or has_secondary or has_company_relevant or has_action))
        or (has_program and (has_tech or has_company_relevant))
        or (has_primary and has_tech and has_action)
    )


def is_government_priority_article(article: Article) -> bool:
    return (
        not is_company_registration_article(article)
        and not is_private_company_government_pr_article(article)
        and not has_any_keyword(article, GOVERNMENT_EXCLUDE_KEYWORDS)
        and not has_any_keyword(article, GOVERNMENT_GENERAL_NOISE_KEYWORDS)
        and has_government_actor(article)
        and has_government_priority_domain(article)
    )


def has_venture_core_content(article: Article) -> bool:
    return text_has_any_keyword(article_text(article), VENTURE_CORE_KEYWORDS)


def has_venture_core_title(article: Article) -> bool:
    return text_has_any_keyword(article.title, VENTURE_CORE_KEYWORDS)


def is_venture_noise(article: Article) -> bool:
    return has_any_keyword(article, VENTURE_NOISE_KEYWORDS) and not has_venture_core_content(article)


def has_venture_weak_only(article: Article) -> bool:
    return has_any_keyword(article, VENTURE_WEAK_KEYWORDS) and not has_venture_core_content(article)


def has_industry_strong_topic(article: Article) -> bool:
    return text_has_any_keyword(article_text(article), INDUSTRY_STRONG_TOPIC_KEYWORDS)


def has_industry_core_content(article: Article) -> bool:
    text = article_text(article)
    return has_industry_strong_topic(article) or (
        text_has_any_keyword(text, INDUSTRY_GENERIC_TECH_KEYWORDS)
        and text_has_any_keyword(text, INDUSTRY_BUSINESS_ACTION_KEYWORDS)
    )


def is_industry_noise(article: Article) -> bool:
    return has_any_keyword(article, INDUSTRY_NOISE_KEYWORDS) and not has_industry_strong_topic(article)


def industry_company_key(article: Article) -> str:
    text = article_text(article).casefold()
    for company, aliases in INDUSTRY_COMPANY_ALIASES.items():
        if any(alias.casefold() in text for alias in aliases):
            return company
    return ""


def hangul_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-z가-힣]", text)
    if not letters:
        return 0.0
    hangul = re.findall(r"[가-힣]", text)
    return len(hangul) / len(letters)


def language_score(article: Article) -> float:
    title_ratio = hangul_ratio(article.title)
    body_ratio = hangul_ratio(article.description)
    if title_ratio >= 0.35:
        return 1.0
    if title_ratio >= 0.15:
        return 0.75
    if body_ratio >= 0.35:
        return 0.55
    return 0.15



def source_score(article: Article) -> float:
    source = source_name(article)
    if source in SOURCE_SCORES:
        return SOURCE_SCORES[source]
    return 0.5


def recency_score(article: Article, now: datetime | None, timezone: str) -> float:
    try:
        tz = get_timezone(timezone)
        localized_now = (now or datetime.now(tz)).astimezone(tz)
        pub_date = article.pub_date.astimezone(tz)
        age_hours = max(0.0, (localized_now - pub_date).total_seconds() / 3600.0)
        return max(0.0, min(1.0, exp(-age_hours / 24.0)))
    except Exception:
        return 0.5


def entity_score(article: Article, category: str) -> float:
    if category != CATEGORY_INNODEP:
        return 0.0
    return 1.0 if has_innodep_title(article) else 0.0


def rule_score(article: Article, category: str) -> float:
    """제목/본문/검색어의 규칙 기반 관련도를 0~1 점수로 계산합니다."""
    title = article.title.casefold()
    description = article.description.casefold()
    query = article.query.casefold()
    score = 0.0
    max_score = 35.0

    for keyword in category_keywords(category):
        needle = keyword.casefold()
        if needle in title:
            score += 3.0
        if needle in description:
            score += 2.0
        if needle and needle in query:
            score += 1.0

    # Category-specific title weights are the strongest rule signal.
    # This keeps generic titles such as "AI 활용" from outranking direct titles
    # such as "AI CCTV", "영상관제", "통합관제센터", or "온디바이스 AI 실증".
    for keyword, weight in category_title_weights(category).items():
        if keyword.casefold() in title:
            score += weight

    # Negative title weights suppress noisy articles that often match broad terms
    # but are not suitable for a company-wide technology/news digest.
    for keyword, weight in negative_title_weights().items():
        if keyword.casefold() in title:
            score += weight

    if category == CATEGORY_INNODEP:
        for entity in IMPORTANT_ENTITIES:
            needle = entity.casefold()
            if needle in title:
                score += 8.0

    for keyword in BLACKLIST_KEYWORDS:
        needle = keyword.casefold()
        if needle in title or needle in description:
            score -= 3.0

    return max(0.0, min(1.0, score / max_score))


def relevance_score(
    article: Article,
    category: str,
    weights: dict[str, float],
    now: datetime | None,
    timezone: str,
) -> tuple[float, dict[str, float]]:
    """규칙, 유사도, 최신성, 출처, 엔티티, 언어 점수를 하나의 추천 점수로 합칩니다."""
    if is_negative_innodep_article(article):
        return 0.0, {
            "rule": 0.0,
            "recency": 0.0,
            "source": 0.0,
            "entity": 0.0,
            "language": 0.0,
            "semantic": 0.0,
            "seed": 0.0,
        }

    rule = rule_score(article, category)
    recency = recency_score(article, now=now, timezone=timezone)
    source = source_score(article)
    entity = entity_score(article, category)
    language = language_score(article)
    total = (
        weights["rule"] * rule
        + weights["recency"] * recency
        + weights["source"] * source
        + weights["entity"] * entity
        + weights["language"] * language
    )
    semantic = semantic_category_score(article, category)
    if semantic is not None:
        total = (1.0 - SEMANTIC_RELEVANCE_BLEND) * total + SEMANTIC_RELEVANCE_BLEND * semantic
    if entity > 0:
        total += 0.30
    if category == CATEGORY_GOVERNMENT and is_government_priority_article(article):
        total += 0.20
    seed = SEED_CATEGORY_BONUS if article.seed_category == category else 0.0
    total += seed
    components = {
        "rule": rule,
        "recency": recency,
        "source": source,
        "entity": entity,
        "language": language,
        "semantic": semantic or 0.0,
        "seed": seed,
    }
    return round(min(1.0, total), 4), components


def threshold_from_min_score(min_score: float) -> float:
    """환경변수 MIN_SCORE를 CCH-MMR 내부의 0~1 후보 통과 기준으로 변환합니다."""
    if min_score <= 0:
        return 0.0
    if min_score <= 1:
        return min_score
    return min(1.0, min_score / 30.0)


def reason_for(article: Article, category: str, components: dict[str, float]) -> str:
    text = article_text(article).casefold()
    title = article.title.casefold()
    matched_title_keywords = [
        keyword for keyword in category_title_weights(category) if keyword.casefold() in title
    ][:3]
    matched_keywords = [keyword for keyword in category_keywords(category) if keyword.casefold() in text][:3]
    parts: list[str] = []
    if matched_title_keywords:
        parts.append(f"제목에 {', '.join(matched_title_keywords)} 핵심 키워드 포함")
    if matched_keywords:
        parts.append(f"{', '.join(matched_keywords)} 키워드가 {category}와 관련")
    if components["recency"] >= 0.35:
        parts.append("최근 발행 기사")
    if components["source"] >= 0.8:
        parts.append("출처 신뢰도 점수가 높음")
    if components.get("entity", 0.0) >= 0.85:
        parts.append("이노뎁 관련성이 높음")
    if components.get("language", 0.0) >= 0.75:
        parts.append("한글 제목 기사")
    if components.get("semantic", 0.0) >= 0.70:
        parts.append("과거 관련 기사와 의미가 유사함")
    return "; ".join(parts[:3])


def category_ranges_from_quotas(category_quotas: dict[str, int] | None) -> dict[str, tuple[int, int]]:
    if category_quotas:
        ranges = {category: (0, 0) for category in CATEGORY_ORDER}
        for category, quota in category_quotas.items():
            normalized_quota = max(0, quota)
            ranges[category] = (normalized_quota, normalized_quota)
        return ranges
    ranges = dict(DEFAULT_CATEGORY_RANGES)
    for category, quota in (category_quotas or {}).items():
        normalized_quota = max(0, quota)
        ranges[category] = (min(normalized_quota, ranges.get(category, (0, normalized_quota))[0]), normalized_quota)
    return ranges


def target_count_for_category(
    candidates: list[tuple[Article, float, dict[str, float]]],
    maximum: int,
    threshold: float,
) -> int:
    """상한 안에서 점수 절벽 이전의 고품질 후보 수만 반환합니다."""
    if maximum <= 0 or not candidates:
        return 0

    best_score = candidates[0][1]
    quality_floor = max(threshold, best_score - QUALITY_SCORE_WINDOW)
    qualified = [candidate for candidate in candidates if candidate[1] >= quality_floor]
    limit = min(maximum, len(qualified))
    for index in range(1, limit):
        previous_score = qualified[index - 1][1]
        current_score = qualified[index][1]
        if previous_score - current_score >= QUALITY_SCORE_CLIFF:
            return index
    return limit


def is_eligible_category_candidate(
    article: Article,
    category: str,
    score: float,
    components: dict[str, float],
    threshold: float,
) -> bool:
    """점수 기준과 카테고리별 필수 조건을 모두 통과하는지 확인합니다."""
    if score < threshold:
        return False
    if category == CATEGORY_INNODEP:
        return has_innodep_title(article)
    if category == CATEGORY_SECURITY:
        if is_security_noise(article):
            return False
        if not has_security_core_content(article):
            return False
        if not has_security_core_title(article):
            return False
    if category == CATEGORY_INDUSTRY:
        if is_industry_noise(article) or not has_industry_core_content(article):
            return False
    if category == CATEGORY_GOVERNMENT:
        if not is_government_priority_article(article):
            return False
        return True
    if category == CATEGORY_VENTURE:
        if is_venture_noise(article) or has_venture_weak_only(article):
            return False
        if not has_venture_core_content(article):
            return False
        if not has_venture_core_title(article) and article.seed_category != CATEGORY_VENTURE:
            return False
    if components.get("entity", 0.0) >= 0.85:
        return True
    if components.get("rule", 0.0) >= 0.15:
        return True
    return False


def is_similar_to_selected(article: Article, selected_articles: list[Article]) -> bool:
    return any(
        title_similarity(article.title, selected.title) >= 0.72
        or is_semantic_duplicate(article, selected)
        for selected in selected_articles
    )


def redundancy_score(left: Article, right: Article) -> float:
    lexical = lexical_cosine(article_text(left), article_text(right))
    semantic = semantic_similarity(left, right)
    if semantic is None:
        return lexical
    normalized_semantic = max(
        0.0,
        min(1.0, (semantic - SEMANTIC_COSINE_FLOOR) / (1.0 - SEMANTIC_COSINE_FLOOR)),
    )
    return (
        (1.0 - SEMANTIC_REDUNDANCY_BLEND) * lexical
        + SEMANTIC_REDUNDANCY_BLEND * normalized_semantic
    )


def better_duplicate(left: Article, right: Article) -> Article:
    left_source = source_score(left)
    right_source = source_score(right)
    if left_source != right_source:
        return left if left_source > right_source else right
    if left.pub_date != right.pub_date:
        return left if left.pub_date > right.pub_date else right
    return left if len(left.title) >= len(right.title) else right


def deduplicate_cch_articles(articles: Iterable[Article]) -> list[Article]:
    unique: list[Article] = []
    by_url: dict[str, int] = {}

    for article in articles:
        url_key = normalize_url(article.canonical_url)
        if url_key in by_url:
            index = by_url[url_key]
            unique[index] = better_duplicate(unique[index], article)
            continue
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(unique)
                if title_similarity(existing.title, article.title) >= 0.85
            ),
            None,
        )
        if duplicate_index is not None:
            unique[duplicate_index] = better_duplicate(unique[duplicate_index], article)
            by_url[url_key] = duplicate_index
            continue
        by_url[url_key] = len(unique)
        unique.append(article)
    return unique


def mmr_select(
    candidates: list[tuple[Article, float, dict[str, float]]],
    quota: int,
    category: str,
    lambda_value: float,
    already_selected: set[str],
    selected_articles: list[Article],
    selected_industry_companies: set[str],
) -> list[Article]:
    """관련도는 높이고, 이미 고른 기사와 너무 비슷한 기사는 피해서 선택합니다."""
    selected: list[Article] = []
    remaining = [
        candidate
        for candidate in candidates
        if candidate[0].canonical_url not in already_selected
        and not is_similar_to_selected(candidate[0], selected_articles)
        and (
            category != CATEGORY_INDUSTRY
            or not industry_company_key(candidate[0])
            or industry_company_key(candidate[0]) not in selected_industry_companies
        )
    ]
    while remaining and len(selected) < quota:
        best_index = 0
        best_score = float("-inf")
        for index, (article, relevance, components) in enumerate(remaining):
            redundancy = 0.0
            comparison_articles = selected_articles + selected
            if comparison_articles:
                redundancy = max(
                    redundancy_score(article, existing) for existing in comparison_articles
                )
            mmr = lambda_value * relevance - (1.0 - lambda_value) * redundancy
            if mmr > best_score:
                best_index = index
                best_score = mmr
        if best_score < MMR_MIN_SELECTION_SCORE:
            break
        article, relevance, components = remaining.pop(best_index)
        selected_article = replace(
            article,
            score=round(relevance, 4),
            category=category,
            reason=reason_for(article, category, components),
        )
        already_selected.add(selected_article.canonical_url)
        selected.append(selected_article)
        if category == CATEGORY_INDUSTRY:
            company = industry_company_key(selected_article)
            if company:
                selected_industry_companies.add(company)
                remaining = [
                    candidate
                    for candidate in remaining
                    if industry_company_key(candidate[0]) != company
                ]
    return selected


def select_cch_mmr_articles(
    articles: list[Article],
    min_score: float,
    max_articles: int,
    timezone: str = "Asia/Seoul",
    now: datetime | None = None,
    weights: dict[str, float] | None = None,
    category_quotas: dict[str, int] | None = None,
    lambda_value: float = 0.70,
    target_categories: list[str] | None = None,
) -> list[Article]:
    """CCH-MMR 추천의 진입점입니다. 점수화, 후보 판정, quota, MMR 선택을 순서대로 수행합니다."""
    if not articles or max_articles <= 0:
        return []

    active_categories = [
        category
        for category in CATEGORY_ORDER
        if target_categories is None or category in target_categories
    ]
    if not active_categories:
        return []

    # 외부에서 일부 가중치만 넘겨도 전체 합이 1이 되도록 정규화합니다.
    active_weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_weight = sum(active_weights.values()) or 1.0
    active_weights = {key: value / total_weight for key, value in active_weights.items()}
    category_ranges = category_ranges_from_quotas(category_quotas)
    threshold = threshold_from_min_score(min_score)
    # 명백한 제외 대상과 중복 기사를 먼저 걷어낸 뒤 카테고리별 점수를 계산합니다.
    unique_articles = [
        article
        for article in deduplicate_cch_articles(articles)
        if not is_blacklisted_article(article)
        and not is_negative_innodep_article(article)
        and not is_private_company_government_pr_article(article)
        and not is_private_company_government_business_article(article)
        and not is_general_government_noise(article)
        and not has_any_keyword(article, GOVERNMENT_EXCLUDE_KEYWORDS)
    ]
    if any(category in ENHANCED_CATEGORIES for category in active_categories):
        prepare_semantic_articles(unique_articles)

    scored_by_category: dict[str, list[tuple[Article, float, dict[str, float]]]] = {category: [] for category in active_categories}
    all_scored: list[tuple[str, Article, float, dict[str, float]]] = []
    for article in unique_articles:
        article_scores: list[tuple[str, Article, float, dict[str, float]]] = []
        for category in active_categories:
            score, components = relevance_score(
                article,
                category,
                weights=active_weights,
                now=now,
                timezone=timezone,
            )
            article_scores.append((category, article, score, components))
        all_scored.extend(article_scores)

        if target_categories is not None:
            for category, _, score, components in article_scores:
                if is_eligible_category_candidate(article, category, score, components, threshold):
                    scored_by_category[category].append((article, score, components))
            continue

        best_category, _, best_score, best_components = max(article_scores, key=lambda item: item[2])
        innodep_score = next(item for item in article_scores if item[0] == CATEGORY_INNODEP)
        if is_eligible_category_candidate(
            innodep_score[1],
            CATEGORY_INNODEP,
            innodep_score[2],
            innodep_score[3],
            threshold,
        ):
            best_category, _, best_score, best_components = innodep_score
        security_score = next(item for item in article_scores if item[0] == CATEGORY_SECURITY)
        if best_category != CATEGORY_INNODEP and is_eligible_category_candidate(
            security_score[1],
            CATEGORY_SECURITY,
            security_score[2],
            security_score[3],
            threshold,
        ):
            best_category, _, best_score, best_components = security_score
        government_score = next(item for item in article_scores if item[0] == CATEGORY_GOVERNMENT)
        venture_score = next(item for item in article_scores if item[0] == CATEGORY_VENTURE)
        venture_is_eligible = is_eligible_category_candidate(
            venture_score[1],
            CATEGORY_VENTURE,
            venture_score[2],
            venture_score[3],
            threshold,
        )
        government_is_eligible = is_eligible_category_candidate(
            government_score[1],
            CATEGORY_GOVERNMENT,
            government_score[2],
            government_score[3],
            threshold,
        )
        prefer_venture_over_government = venture_is_eligible and (
            article.seed_category == CATEGORY_VENTURE
            or has_venture_core_title(article)
            or venture_score[2] >= government_score[2] - 0.08
        )
        if best_category != CATEGORY_INNODEP and government_is_eligible and not prefer_venture_over_government:
            best_category, _, best_score, best_components = government_score
        if best_category != CATEGORY_INNODEP and prefer_venture_over_government:
            best_category, _, best_score, best_components = venture_score
        if is_eligible_category_candidate(article, best_category, best_score, best_components, threshold):
            scored_by_category[best_category].append((article, best_score, best_components))

    for category in active_categories:
        scored_by_category[category].sort(key=lambda item: (-item[1], item[0].pub_date))

    selected: list[Article] = []
    selected_urls: set[str] = set()
    selected_industry_companies: set[str] = set()
    selected_counts: dict[str, int] = {category: 0 for category in active_categories}
    for category in active_categories:
        remaining_slots = max_articles - len(selected)
        if remaining_slots <= 0:
            break
        _, maximum = category_ranges.get(category, (0, 0))
        target_count = target_count_for_category(
            scored_by_category[category],
            maximum=maximum,
            threshold=threshold,
        )
        target_count = min(target_count, remaining_slots)
        if target_count <= 0:
            continue
        category_selected = mmr_select(
            scored_by_category[category],
            quota=target_count,
            category=category,
            lambda_value=lambda_value,
            already_selected=selected_urls,
            selected_articles=selected,
            selected_industry_companies=selected_industry_companies,
        )
        selected_counts[category] += len(category_selected)
        selected.extend(category_selected)

    return selected[:max_articles]
