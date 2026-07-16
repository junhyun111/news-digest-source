from __future__ import annotations

from urllib.parse import urlsplit

from .models import Article


CATEGORY_SECURITY = "\ubcf4\uc548 \uad00\ub828 \uae30\uc0ac"
CATEGORY_INNODEP = "이노뎁 관련 기사"
CATEGORY_INDUSTRY = "\uc5c5\uacc4 \ub3d9\ud5a5 \uae30\uc0ac"
CATEGORY_GOVERNMENT = "\uc815\ubd80/\uacf5\uacf5 \uae30\uc0ac"
CATEGORY_VENTURE = "\ubca4\ucc98/\uae08\uc735 \uae30\uc0ac"
CATEGORY_LABOR = "\uc0dd\uc0b0/\uc784\uae08 \uae30\uc0ac"

CATEGORY_ORDER = [
    CATEGORY_INNODEP,
    CATEGORY_SECURITY,
    CATEGORY_INDUSTRY,
    CATEGORY_GOVERNMENT,
    CATEGORY_VENTURE,
    CATEGORY_LABOR,
]

CATEGORY_KEYWORDS = {
    CATEGORY_INNODEP: [
        "이노뎁",
        "innodep",
    ],
    CATEGORY_SECURITY: [
        "cctv",
        "vms",
        "nvr",
        "\ud55c\ud654\ube44\uc804",
        "관제",
        "통합관제",
        "영상관제",
        "관제센터",
        "영상보안",
        "영상분석",
        "방범카메라",
        "보안카메라",
        "출입통제",
    ],
    CATEGORY_GOVERNMENT: [
        "\uc815\ubd80",
        "\uacf5\uacf5",
        "\uc11c\uc6b8\uc2dc",
        "\uacbd\ubd81",
        "\uacbd\uae30\ub3c4",
        "\ud589\uc815",
        "\ub3c4\ub85c\uad50\ud1b5",
        "\uad50\ud1b5\uccb4\uacc4",
        "\uad6d\uac00\uc0b0\ub2e8",
        "\uc2dc\ubbfc",
        "국토부",
        "교통",
        "공공조달",
        "중진공",
    ],
    CATEGORY_VENTURE: [
        "\uc2a4\ud0c0\ud2b8\uc5c5",
        "\ubca4\ucc98",
        "\ud22c\uc790",
        "\ud380\ub4dc",
        "\uae08\uc735",
        "startup",
        "venture",
        "fund",
        "finance",
        "investment",
        "ipo",
        "\uc0b0\uc5c5\uc740\ud589",
        "\ub124\uc774\ubc84\ud398\uc774",
        "\uc720\ub2c8\ucf58",
        "\ubaa8\ud5d8\uc790\ubcf8",
        "창업",
        "상장",
        "딥테크",
        "코스닥",
    ],
    CATEGORY_LABOR: [
        "\ucd5c\uc800\uc784\uae08",
        "\uc784\uae08",
        "\ub178\uc0ac",
        "\uac10\uc6d0",
        "\uc77c\uc790\ub9ac",
        "\uadfc\ub85c\uc790",
        "\uc0dd\uc0b0",
        "업종별",
        "인상",
        "시급",
        "소상공인",
    ],
    CATEGORY_INDUSTRY: [
        "온디바이스 ai",
        "엣지 ai",
        "피지컬 ai",
        "에이전틱 ai",
        "ai 에이전트",
        "ai 반도체",
        "ai 가속기",
        "ai 인프라",
        "ai 데이터센터",
        "컴퓨터비전",
        "영상분석",
        "스마트시티",
        "지능형교통",
        "스마트팩토리",
        "디지털트윈",
        "자율주행",
        "로봇",
        "휴머노이드",
        "gpu",
    ],
}

SOURCE_NAMES = {
    "etnews.com": "\uc804\uc790\uc2e0\ubb38",
    "yna.co.kr": "\uc5f0\ud569\ub274\uc2a4",
    "edaily.co.kr": "\uc774\ub370\uc77c\ub9ac",
    "fnnews.com": "\ud30c\uc774\ub0b8\uc15c\ub274\uc2a4",
    "khan.co.kr": "\uacbd\ud5a5\uc2e0\ubb38",
    "mk.co.kr": "\ub9e4\uc77c\uacbd\uc81c",
    "viva100.com": "\ube0c\ub9bf\uc9c0\uacbd\uc81c",
    "donga.com": "\ub3d9\uc544\uc77c\ubcf4",
    "seoul.co.kr": "\uc11c\uc6b8\uc2e0\ubb38",
    "dt.co.kr": "\ub514\uc9c0\ud138\ud0c0\uc784\uc2a4",
    "mt.co.kr": "\uba38\ub2c8\ud22c\ub370\uc774",
    "hankyung.com": "\ud55c\uad6d\uacbd\uc81c",
    "chosun.com": "\uc870\uc120\uc77c\ubcf4",
    "dnews.co.kr": "\ub300\ud55c\uacbd\uc81c",
    "sedaily.com": "\uc11c\uc6b8\uacbd\uc81c",
}


def classify_article(article: Article) -> str:
    text = f"{article.title} {article.description} {article.query}".casefold()
    best_category = CATEGORY_INDUSTRY
    best_score = 0

    for category in CATEGORY_ORDER:
        score = sum(1 for keyword in CATEGORY_KEYWORDS[category] if keyword.casefold() in text)
        if score > best_score:
            best_category = category
            best_score = score

    return best_category


def source_name(article: Article) -> str:
    host = urlsplit(article.canonical_url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    for domain, name in SOURCE_NAMES.items():
        if host == domain or host.endswith(f".{domain}"):
            return name
    return host or "\ucd9c\ucc98"
