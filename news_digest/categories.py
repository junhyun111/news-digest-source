from __future__ import annotations

from urllib.parse import urlsplit

from .models import Article


CATEGORY_SECURITY = "보안 관련 기사"
CATEGORY_INNODEP = "이노뎁 관련 기사"
CATEGORY_INDUSTRY = "업계 동향 기사"
CATEGORY_GOVERNMENT = "정부/공공 기사"
CATEGORY_VENTURE = "벤처/금융 기사"
CATEGORY_LABOR = "생산/임금 기사"

CATEGORY_ORDER = [
    CATEGORY_INNODEP,
    CATEGORY_SECURITY,
    CATEGORY_INDUSTRY,
    CATEGORY_GOVERNMENT,
    CATEGORY_VENTURE,
    CATEGORY_LABOR,
]

SOURCE_NAMES = {
    "etnews.com": "전자신문",
    "yna.co.kr": "연합뉴스",
    "edaily.co.kr": "이데일리",
    "fnnews.com": "파이낸셜뉴스",
    "khan.co.kr": "경향신문",
    "mk.co.kr": "매일경제",
    "viva100.com": "브릿지경제",
    "donga.com": "동아일보",
    "seoul.co.kr": "서울신문",
    "dt.co.kr": "디지털타임스",
    "mt.co.kr": "머니투데이",
    "hankyung.com": "한국경제",
    "chosun.com": "조선일보",
    "dnews.co.kr": "대한경제",
    "sedaily.com": "서울경제",
}


def source_name(article: Article) -> str:
    host = urlsplit(article.canonical_url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    for domain, name in SOURCE_NAMES.items():
        if host == domain or host.endswith(f".{domain}"):
            return name
    return host or "출처"
