from __future__ import annotations

from .categories import (
    CATEGORY_GOVERNMENT,
    CATEGORY_INDUSTRY,
    CATEGORY_INNODEP,
    CATEGORY_LABOR,
    CATEGORY_SECURITY,
    CATEGORY_VENTURE,
)


NEWS_QUERIES = [
    "AI",
    "인공지능",
    "생성형 AI",
    "반도체",
    "보안",
    "클라우드",
    "데이터센터",
]

CATEGORY_QUERIES = {
    CATEGORY_INNODEP: [
        "이노뎁",
        "innodep",
    ],
    CATEGORY_SECURITY: [
        "AI CCTV",
        "지능형 CCTV",
        "CCTV 관제",
        "지능형 관제",
        "영상관제",
        "통합관제센터",
        "AI 영상분석",
        "영상보안",
        "물리보안",
        "실시간 관제",
        "화재 감지 CCTV",
    ],
    CATEGORY_INDUSTRY: [
        "온디바이스 AI",
        "엣지 AI",
        "피지컬 AI",
        "에이전틱 AI",
        "AI 에이전트",
        "오픈AI",
        "챗GPT",
        "엔비디아 AI",
        "AI 반도체",
        "자율주행 AI",
        "컴퓨터비전",
        "스마트시티",
        "디지털트윈",
        "로봇 자동화",
    ],
    CATEGORY_GOVERNMENT: [
        "공공 AI",
        "지자체 AI",
        "AI 공모사업",
        "AI 시범사업",
        "공공조달 AI",
        "나라장터 AI",
        "국책과제 AI",
        "스마트시티 실증",
        "디지털플랫폼정부 AI",
        "조달청 AI CCTV",
        "국토부 AI",
        "과기정통부 AI",
        "NIPA AI",
        "NIA AI",
        "IITP AI",
    ],
    CATEGORY_VENTURE: [
        "AI 스타트업 투자유치",
        "보안 스타트업 투자유치",
        "스마트시티 스타트업",
        "딥테크 투자유치",
        "벤처 투자유치",
        "TIPS AI 스타트업",
        "모태펀드 스타트업",
        "유니콘 스타트업",
        "중진공 AI 스타트업",
        "AI 기술특례상장",
        "정책금융 스타트업",
    ],
    CATEGORY_LABOR: [
        "최저임금",
        "임금협상",
        "근로기준법",
        "노동자성",
        "노사",
        "임단협",
        "근로시간",
        "인건비",
    ],
}

KEYWORD_WEIGHTS = {
    "AI": 2,
    "인공지능": 2,
    "보안": 3,
    "CCTV": 4,
    "스마트시티": 4,
}

TITLE_KEYWORD_WEIGHTS = {
    "AI CCTV": 12,
    "지능형 CCTV": 12,
    "영상관제": 10,
    "통합관제": 10,
    "통합관제센터": 11,
    "VMS": 10,
    "AI 영상분석": 10,
    "온디바이스 AI": 9,
    "엣지 AI": 9,
    "스마트시티": 9,
    "디지털트윈": 8,
    "피지컬 AI": 8,
    "에이전틱 AI": 8,
    "공공조달": 8,
    "실증사업": 7,
    "국책과제": 7,
    "스타트업 투자": 7,
    "투자유치": 7,
    "최저임금": 8,
    "임금협상": 8,
}

CATEGORY_TITLE_WEIGHTS = {
    CATEGORY_INDUSTRY: {
        "온디바이스 AI": 12,
        "엣지 AI": 11,
        "피지컬 AI": 10,
        "에이전틱 AI": 10,
        "AI 에이전트": 10,
        "생성형 AI": 8,
        "NPU": 8,
        "GPU": 7,
        "컴퓨터비전": 10,
        "영상분석": 10,
        "스마트시티": 10,
        "디지털트윈": 9,
        "로봇": 7,
        "휴머노이드": 8,
        "자율주행": 7,
        "SDV": 7,
        "클라우드": 6,
        "데이터센터": 6,
        "국제표준": 8,
        "상용화": 7,
        "실증": 7,
        "도입": 6,
        "공동 개발": 6,
        "협력": 5,
    },
}

NEGATIVE_TITLE_WEIGHTS = {
    "칼럼": -12,
    "취임 인터뷰": -10,
    "Who Is": -10,
    "부동산": -8,
    "주가": -8,
    "실적": -5,
    "성과급 갈등": -5,
    "연예": -15,
    "스포츠": -15,
    "맛집": -15,
    "날씨": -15,
    "여행": -12,
    "운세": -15,
}

MIN_SCORE = 12.0
MAX_ARTICLES = 25
TIMEZONE = "Asia/Seoul"
TEST_MODE = False
USE_SAMPLE_DATA = False
SMTP_HOST = "smtp.naver.com"
SMTP_PORT = 587
MMR_LAMBDA = 0.70
RECOMMENDATION_WEIGHTS = {}
CATEGORY_QUOTAS = {}


def validate_settings() -> None:
    if not NEWS_QUERIES:
        raise ValueError("NEWS_QUERIES must not be empty.")
    for category, queries in CATEGORY_QUERIES.items():
        if not queries:
            raise ValueError(f"CATEGORY_QUERIES[{category!r}] must not be empty.")
    if MIN_SCORE < 0:
        raise ValueError("MIN_SCORE must be greater than or equal to 0.")
    if MAX_ARTICLES <= 0:
        raise ValueError("MAX_ARTICLES must be greater than 0.")
    if not 1 <= SMTP_PORT <= 65535:
        raise ValueError("SMTP_PORT must be between 1 and 65535.")
    if not 0 <= MMR_LAMBDA <= 1:
        raise ValueError("MMR_LAMBDA must be between 0 and 1.")
