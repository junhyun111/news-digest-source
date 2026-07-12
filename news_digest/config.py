from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
import os

from . import settings
from .categories import (
    CATEGORY_GOVERNMENT,
    CATEGORY_INDUSTRY,
    CATEGORY_INNODEP,
    CATEGORY_LABOR,
    CATEGORY_SECURITY,
    CATEGORY_VENTURE,
)


DEFAULT_QUERIES = settings.NEWS_QUERIES
DEFAULT_CATEGORY_QUERIES = settings.CATEGORY_QUERIES

CATEGORY_QUERY_ENV_NAMES = {
    CATEGORY_INNODEP: "INNODEP_QUERIES",
    CATEGORY_SECURITY: "SECURITY_QUERIES",
    CATEGORY_INDUSTRY: "INDUSTRY_QUERIES",
    CATEGORY_GOVERNMENT: "GOVERNMENT_QUERIES",
    CATEGORY_VENTURE: "VENTURE_QUERIES",
    CATEGORY_LABOR: "LABOR_QUERIES",
}

DEFAULT_KEYWORD_WEIGHTS = settings.KEYWORD_WEIGHTS
DEFAULT_MIN_SCORE = settings.MIN_SCORE
DEFAULT_MAX_ARTICLES = settings.MAX_ARTICLES
DEFAULT_TIMEZONE = settings.TIMEZONE
DEFAULT_TEST_MODE = settings.TEST_MODE
DEFAULT_USE_SAMPLE_DATA = settings.USE_SAMPLE_DATA
DEFAULT_SMTP_HOST = settings.SMTP_HOST
DEFAULT_SMTP_PORT = settings.SMTP_PORT
DEFAULT_MMR_LAMBDA = settings.MMR_LAMBDA


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip().lstrip("\ufeff"), value.strip().strip('"').strip("'"))


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_keyword_weights(value: str | None) -> dict[str, float]:
    weights: dict[str, float] = {}
    for item in parse_csv(value):
        if ":" in item:
            keyword, raw_weight = item.rsplit(":", 1)
            try:
                weights[keyword.strip()] = float(raw_weight.strip())
            except ValueError:
                weights[keyword.strip()] = 1.0
        else:
            weights[item] = 1.0
    return weights


def parse_float_map(value: str | None) -> dict[str, float]:
    return parse_keyword_weights(value)


def parse_int_map(value: str | None) -> dict[str, int]:
    values: dict[str, int] = {}
    for item in parse_csv(value):
        if ":" not in item:
            continue
        key, raw_value = item.rsplit(":", 1)
        try:
            values[key.strip()] = int(raw_value.strip())
        except ValueError:
            continue
    return values


def parse_category_queries() -> dict[str, list[str]]:
    queries: dict[str, list[str]] = {}
    for category, env_name in CATEGORY_QUERY_ENV_NAMES.items():
        category_queries = parse_csv(os.getenv(env_name)) or DEFAULT_CATEGORY_QUERIES[category]
        queries[category] = list(category_queries)
    return queries


@dataclass(frozen=True)
class Config:
    naver_client_id: str
    naver_client_secret: str
    queries: list[str]
    keyword_weights: dict[str, float]
    min_score: float
    max_articles: int
    timezone: str
    test_mode: bool
    use_sample_data: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    mail_sender: str
    real_recipients: list[str]
    test_recipients: list[str]
    category_queries: dict[str, list[str]] = field(default_factory=dict)
    recommendation_weights: dict[str, float] = field(default_factory=dict)
    category_quotas: dict[str, int] = field(default_factory=dict)
    mmr_lambda: float = DEFAULT_MMR_LAMBDA

    @property
    def recipients(self) -> list[str]:
        return self.test_recipients if self.test_mode else self.real_recipients

    @classmethod
    def from_env(cls) -> "Config":
        settings.validate_settings()
        load_dotenv()
        category_queries = parse_category_queries()
        queries = parse_csv(os.getenv("NEWS_QUERIES"))
        if not queries:
            queries = DEFAULT_QUERIES
        keyword_weights = parse_keyword_weights(os.getenv("KEYWORD_WEIGHTS"))
        if not keyword_weights:
            keyword_weights = DEFAULT_KEYWORD_WEIGHTS

        has_naver_credentials = bool(
            os.getenv("NAVER_CLIENT_ID") and os.getenv("NAVER_CLIENT_SECRET")
        )
        use_sample_default = not has_naver_credentials

        return cls(
            naver_client_id=os.getenv("NAVER_CLIENT_ID", ""),
            naver_client_secret=os.getenv("NAVER_CLIENT_SECRET", ""),
            queries=queries,
            keyword_weights=keyword_weights,
            min_score=float(os.getenv("MIN_SCORE", str(DEFAULT_MIN_SCORE))),
            max_articles=int(os.getenv("MAX_ARTICLES", str(DEFAULT_MAX_ARTICLES))),
            timezone=os.getenv("TIMEZONE", DEFAULT_TIMEZONE),
            test_mode=parse_bool(os.getenv("TEST_MODE"), default=DEFAULT_TEST_MODE),
            use_sample_data=parse_bool(
                os.getenv("USE_SAMPLE_DATA"),
                default=use_sample_default if use_sample_default else DEFAULT_USE_SAMPLE_DATA,
            ),
            smtp_host=os.getenv("SMTP_HOST", DEFAULT_SMTP_HOST),
            smtp_port=int(os.getenv("SMTP_PORT", str(DEFAULT_SMTP_PORT))),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            mail_sender=os.getenv("MAIL_SENDER", ""),
            real_recipients=parse_csv(os.getenv("REAL_RECIPIENTS")),
            test_recipients=parse_csv(os.getenv("TEST_RECIPIENTS")),
            category_queries=category_queries,
            recommendation_weights=parse_float_map(os.getenv("RECOMMENDATION_WEIGHTS"))
            or settings.RECOMMENDATION_WEIGHTS,
            category_quotas=parse_int_map(os.getenv("CATEGORY_QUOTAS")) or settings.CATEGORY_QUOTAS,
            mmr_lambda=float(os.getenv("MMR_LAMBDA", str(DEFAULT_MMR_LAMBDA))),
        )
