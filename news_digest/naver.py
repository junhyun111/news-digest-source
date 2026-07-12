from __future__ import annotations

from datetime import datetime, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from html import unescape
import json
import logging
import re
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Article
from .timezones import get_timezone

LOGGER = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")
REQUEST_INTERVAL_SECONDS = 0.3
MAX_RATE_LIMIT_RETRIES = 5
_last_request_at = 0.0


def wait_for_request_slot() -> None:
    """Keep requests from this Lambda runtime below a conservative rate."""
    global _last_request_at

    elapsed = time.monotonic() - _last_request_at
    remaining = REQUEST_INTERVAL_SECONDS - elapsed
    if remaining > 0:
        time.sleep(remaining)
    _last_request_at = time.monotonic()


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return TAG_RE.sub("", unescape(text)).strip()


def parse_pub_date(value: Any, timezone: str = "Asia/Seoul") -> datetime:
    if not value:
        raise ValueError("pubDate is missing")
    parsed = parsedate_to_datetime(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=get_timezone(timezone))
    return parsed.astimezone(get_timezone(timezone))


def parse_naver_item(
    item: dict[str, Any],
    query: str = "",
    timezone: str = "Asia/Seoul",
    seed_category: str = "",
) -> Article:
    return Article(
        title=clean_text(item.get("title")),
        description=clean_text(item.get("description")),
        originallink=str(item.get("originallink") or "").strip(),
        link=str(item.get("link") or "").strip(),
        pub_date=parse_pub_date(item.get("pubDate"), timezone),
        query=query,
        seed_category=seed_category,
    )


def parse_naver_response(
    payload: dict[str, Any],
    query: str = "",
    timezone: str = "Asia/Seoul",
    seed_category: str = "",
) -> list[Article]:
    articles: list[Article] = []
    for item in payload.get("items", []):
        try:
            article = parse_naver_item(
                item,
                query=query,
                timezone=timezone,
                seed_category=seed_category,
            )
        except Exception:
            LOGGER.exception("Skipping malformed Naver item: %r", item)
            continue
        if article.title and article.canonical_url:
            articles.append(article)
    return articles


def fetch_naver_news(
    client_id: str,
    client_secret: str,
    query: str,
    display: int = 100,
    sort: str = "date",
) -> dict[str, Any]:
    if not client_id or not client_secret:
        raise ValueError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required")

    params = urlencode({"query": query, "display": display, "sort": sort})
    request = Request(
        f"https://openapi.naver.com/v1/search/news.json?{params}",
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        wait_for_request_slot()

        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code != 429 or attempt >= MAX_RATE_LIMIT_RETRIES:
                LOGGER.error(
                    "Naver API request failed: status=%s query=%r body=%s",
                    exc.code,
                    query,
                    error_body,
                )
                raise

            LOGGER.warning(
                "Naver API rate limited: query=%r retry=%s/%s delay=%.1fs body=%s",
                query,
                attempt + 1,
                MAX_RATE_LIMIT_RETRIES,
                REQUEST_INTERVAL_SECONDS,
                error_body,
            )
            time.sleep(REQUEST_INTERVAL_SECONDS)

    raise RuntimeError("Naver API retry loop ended unexpectedly")


def sample_payload(timezone: str = "Asia/Seoul") -> dict[str, Any]:
    tz = get_timezone(timezone)
    yesterday = datetime.now(tz).date() - timedelta(days=1)
    yesterday_noon = datetime.combine(yesterday, datetime.min.time(), tz) + timedelta(hours=12)
    two_days_ago = yesterday_noon - timedelta(days=1)
    return {
        "items": [
            {
                "title": "Generative AI security investment expands",
                "description": "Companies are increasing AI security and data protection investment.",
                "originallink": "https://example.com/news/ai-security",
                "link": "https://n.news.naver.com/mnews/article/001/0000000001",
                "pubDate": format_datetime(yesterday_noon),
            },
            {
                "title": "Generative AI security investment expands",
                "description": "Duplicate article with the same normalized title.",
                "originallink": "https://example.com/news/ai-security-copy",
                "link": "https://n.news.naver.com/mnews/article/001/0000000002",
                "pubDate": format_datetime(yesterday_noon),
            },
            {
                "title": "Semiconductor cloud infrastructure partnership",
                "description": "Chip and cloud companies announced data center cooperation.",
                "originallink": "https://example.com/news/chip-cloud",
                "link": "https://n.news.naver.com/mnews/article/001/0000000003",
                "pubDate": format_datetime(yesterday_noon),
            },
            {
                "title": "Old article",
                "description": "This article is not from yesterday and should be excluded.",
                "originallink": "https://example.com/news/old",
                "link": "https://n.news.naver.com/mnews/article/001/0000000004",
                "pubDate": format_datetime(two_days_ago),
            },
        ]
    }
