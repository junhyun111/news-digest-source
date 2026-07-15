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
    CATEGORY_LABOR,
    CATEGORY_ORDER,
    CATEGORY_SECURITY,
    CATEGORY_VENTURE,
    source_name,
)
from .models import Article
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

DEFAULT_WEIGHTS = {
    # 최종 추천 점수에서 각 신호가 차지하는 기본 비중
    "rule": 0.38,
    "recency": 0.08,
    "source": 0.02,
    "entity": 0.15,
    "language": 0.08,
}

SEED_CATEGORY_BONUS = 0.05
SEMANTIC_RELEVANCE_BLEND = 0.35
SEMANTIC_REDUNDANCY_BLEND = 0.75
SEMANTIC_COSINE_FLOOR = 0.35

DEFAULT_CATEGORY_QUOTAS = {
    CATEGORY_INNODEP: 2,
    CATEGORY_SECURITY: 4,
    CATEGORY_INDUSTRY: 12,
    CATEGORY_GOVERNMENT: 3,
    CATEGORY_VENTURE: 4,
    CATEGORY_LABOR: 2,
}

DEFAULT_CATEGORY_RANGES = {
    CATEGORY_INNODEP: (0, 2),
    CATEGORY_SECURITY: (4, 8),
    CATEGORY_INDUSTRY: (10, 15),
    CATEGORY_GOVERNMENT: (0, 3),
    CATEGORY_VENTURE: (0, 4),
    CATEGORY_LABOR: (0, 2),
}

DEFAULT_GLOBAL_TITLE_WEIGHTS = {
    "AI": 12.0,
    "인공지능": 12.0,
}

DEFAULT_CATEGORY_TITLE_WEIGHTS = {
    CATEGORY_INNODEP: {
        "이노뎁": 15.0,
        "innodep": 15.0,
    },
    CATEGORY_SECURITY: {
        "AI CCTV": 15.0,
        "지능형 CCTV": 15.0,
        "방범 CCTV": 14.0,
        "영상관제": 13.0,
        "통합관제": 13.0,
        "통합관제센터": 14.0,
        "VMS": 12.0,
        "NVR": 11.0,
        "CCTV": 10.0,
        "영상보안": 12.0,
        "지능형 영상분석": 12.0,
        "이상행동 감지": 11.0,
        "방범카메라": 10.0,
        "보안카메라": 10.0,
        "출입통제": 9.0,
        "화재감지": 8.0,
        "화재 감지": 8.0,
        "침입감지": 9.0,
        "침입 감지": 9.0,
    },
    CATEGORY_INDUSTRY: {
        "온디바이스 AI": 12.0,
        "엣지 AI": 11.0,
        "피지컬 AI": 11.0,
        "에이전틱 AI": 11.0,
        "AI 에이전트": 10.0,
        "NPU": 8.0,
        "GPU": 7.0,
        "AI 반도체": 10.0,
        "AI 가속기": 10.0,
        "AI 인프라": 9.0,
        "AI 플랫폼": 9.0,
        "컴퓨터비전": 10.0,
        "영상분석": 10.0,
        "AI 영상분석": 11.0,
        "스마트시티": 10.0,
        "스마트 시티": 10.0,
        "스마트도시": 10.0,
        "스마트 도시": 10.0,
        "지능형교통": 9.0,
        "지능형 교통": 9.0,
        "스마트팩토리": 9.0,
        "스마트 팩토리": 9.0,
        "디지털트윈": 9.0,
        "로봇": 7.0,
        "휴머노이드": 8.0,
        "자율주행": 7.0,
        "SDV": 7.0,
        "AI 클라우드": 8.0,
        "AI 데이터센터": 9.0,
        "국제표준": 8.0,
        "상용화": 7.0,
        "실증": 7.0,
        "도입": 6.0,
        "출시": 7.0,
        "공급": 7.0,
        "수주": 8.0,
        "자동화": 6.0,
        "엔비디아": 8.0,
        "AX": 7.0,
        "반도체": 7.0,
    },
    CATEGORY_GOVERNMENT: {
        "정부": 5.0,
        "중긴공": 6.0,
        "경기도": 6.0,
        "과기정통부": 7.0,
        "과학기술정보통신부": 7.0,
        "산업통상자원부": 7.0,
        "산업부": 7.0,
        "공모": 7.0,
        "스마트시티": 8.0,
        "스마트도시": 8.0,
        "통합관제센터": 9.0,
        "재난안전": 7.0,
        "도시안전": 7.0,
        "교통체계": 7.0,
        "중진공": 6.0,
        "AI 지원": 7.0,
    },
    CATEGORY_VENTURE: {
        "스타트업": 10.0,
        "k스타트업" : 9.0,
        "ipo": 8.0,
        "IPO": 8.0,
        "벤처": 8.0,
        "벤처기업" : 8.0,
        "투자유치": 8.0,
        "투자 유치": 8.0,
        "상장": 8.0,
        "창업": 8.0,
        "중기부": 8.0,
        "딥테크": 8.0,
        "코스닥": 7.0,
        "PEF": 7.0,
        "생태계": 6.0,
   
    },
    CATEGORY_LABOR: {
        "최저임금": 12.0,
        "임금협상": 11.0,
        "임금": 7.0,
        "노사": 8.0,
        "근로기준법": 9.0,
        "노동자": 8.0,
        "고용노동부": 8.0,
        "근로시간": 8.0,
        "인건비": 8.0,
        "감원": 7.0,
        "구조조정": 7.0,
        "업종별": 8.0,
        "인상": 7.0,
        "시급": 7.0,
        "소상공인": 6.0,
    },
}

CATEGORY_TITLE_ENV_NAMES = {
    CATEGORY_INNODEP: "INNODEP_TITLE_WEIGHTS",
    CATEGORY_SECURITY: "SECURITY_TITLE_WEIGHTS",
    CATEGORY_INDUSTRY: "INDUSTRY_TITLE_WEIGHTS",
    CATEGORY_GOVERNMENT: "GOVERNMENT_TITLE_WEIGHTS",
    CATEGORY_VENTURE: "VENTURE_TITLE_WEIGHTS",
    CATEGORY_LABOR: "LABOR_TITLE_WEIGHTS",
}

DEFAULT_NEGATIVE_TITLE_WEIGHTS = {
    "칼럼": -12.0,
    "취임 인터뷰": -10.0,
    "Who Is": -10.0,
    "부동산": -8.0,
    "주가 급등": -8.0,
    "테마주": -8.0,
    "주요공시": -8.0,
    "실적": -5.0,
    "성과급 갈등": -4.0,
    "연예": -15.0,
    "스포츠": -15.0,
    "맛집": -15.0,
    "날씨": -15.0,
    "여행": -12.0,
    "운세": -15.0,
}


CATEGORY_KEYWORDS = {
    CATEGORY_INNODEP: [
        "이노뎁",
        "innodep",
    ],
    CATEGORY_SECURITY: [
        "CCTV",
        "VMS",
        "NVR",
        "영상관제",
        "관제",
        "통합관제",
        "통합관제센터",
        "관제센터",
        "물리보안",
        "영상보안",
        "출입통제",
        "지능형 관제",
        "지능형 영상분석",
        "영상분석",
        "AI CCTV",
        "ONVIF",
        "영상정보",
        "시설 관제",
        "스마트 치안",
        "방범카메라",
        "방범 카메라",
        "보안카메라",
        "보안 카메라",
        "이상행동 감지",
        "침입감지",
        "침입 감지",
        "화재감지 CCTV",
        "화재 감지 CCTV",
    ],
    CATEGORY_INDUSTRY: [
        "스마트시티",
        "영상보안",
        "통합관제",
        "AI 영상분석",
        "온디바이스 AI",
        "엣지 AI",
        "엣지 컴퓨팅",
        "피지컬 AI",
        "에이전틱 AI",
        "AI 에이전트",
        "AI 반도체",
        "AI 가속기",
        "AI 인프라",
        "AI 데이터센터",
        "디지털트윈",
        "관제 플랫폼",
        "지능형교통",
        "지능형 교통",
        "스마트팩토리",
        "스마트 팩토리",
        "자동화",
        "로봇",
        "휴머노이드",
        "자율주행",
        "컴퓨터비전",
        "NPU",
        "GPU",
        "출시",
        "상용화",
        "도입",
        "구축",
        "공급",
        "수주",
        "실증",
        "제휴",
        "협력",
    ],
    CATEGORY_GOVERNMENT: [
        "과학기술정보통신부",
        "행정안전부",
        "행안부",
        "KISA",
        "지자체",
        "지방자치단체",
        "스마트시티",
        "통합관제센터",
        "도시안전",
        "디지털플랫폼정부",
        "재난안전",
        "공공기관",
        "CCTV 예산",
        "공모사업",
        "입찰",
        "정부",
        "공공",
        "규제",
        "정책",
        "지자체 공모",
        "공모",
        "공공 인프라",
        "공공인프라",
        "공공 사업",
        "공공사업",
        "예산",
        "국책",
        "시범사업",
        "국토부",
        "국토교통부",
        "서울시",
        "교통",
        "중진공",
        "중소기업",
        "AI 지원",
        "공공조달",
    ],
    CATEGORY_VENTURE: [
        "스타트업",
        "벤처",
        "벤처투자",
        "투자유치",
        "투자 유치",
        "시리즈A",
        "시리즈B",
        "프리A",
        "프리IPO",
        "IPO",
        "기술특례",
        "기술특례상장",
        "M&A",
        "VC",
        "벤처캐피탈",
        "벤처 캐피탈",
        "액셀러레이터",
        "오픈이노베이션",
        "스케일업",
        "TIPS",
        "팁스",
        "청창사",
        "창업성공패키지",
        "창업진흥원",
        "중진공",
        "중소벤처기업진흥공단",
        "중소벤처기업부",
        "중기부",
        "모태펀드",
        "정책금융",
        "산업은행",
        "한국벤처투자",
        "KVIC",
        "보안 스타트업",
        "AI 스타트업",
        "스마트시티 스타트업",
        "딥테크",
        "공공 SaaS",
        "상장",
        "창업",
        "성장",
        "유니콘",
        "생태계",
        "코스닥",
        "PEF",
        "자금",
        "MOU",
    ],
    CATEGORY_LABOR: [
        "최저임금",
        "임금협상",
        "근로시간",
        "고용노동부",
        "인건비",
        "노무관리",
        "산업안전",
        "개발자 임금",
        "IT 인력",
        "고용정책",
        "임금",
        "노사",
        "거시경제",
        "노동 정책",
        "노동정책",
        "노사 관계",
        "노사관계",
        "고용",
        "업종별",
        "인상",
        "심의",
        "경영계",
        "노동계",
        "소상공인",
        "시급",
        "물가",
    ],
}

BLACKLIST_KEYWORDS = [
    "연예",
    "스포츠",
    "맛집",
    "여행",
    "날씨",
    "weather",
    "운세",
    "주요공시",
    "패트롤",
]
INNODEP_ENTITIES = ["이노뎁", "innodep"]
INNODEP_NEGATIVE_KEYWORDS = [
    "압수수색",
    "수사",
    "기소",
    "횡령",
    "배임",
    "제재",
    "과징금",
    "벌금",
    "소송",
    "분쟁",
    "하락",
    "급락",
    "적자",
    "손실",
    "부진",
    "리콜",
    "장애",
    "먹통",
    "유출",
    "해킹",
    "사고",
    "논란",
]

SECURITY_CORE_KEYWORDS = [
    "cctv",
    "vms",
    "nvr",
    "통합관제",
    "관제센터",
    "영상관제",
    "영상보안",
    "영상분석",
    "출입통제",
    "물리보안",
    "시설 보안",
    "시설 관제",
    "방범카메라",
    "방범 카메라",
    "보안카메라",
    "보안 카메라",
    "이상행동 감지",
    "침입감지",
    "침입 감지",
    "화재감지 cctv",
    "화재 감지 cctv",
]

SECURITY_TITLE_CORE_KEYWORDS = [
    "cctv",
    "vms",
    "nvr",
    "통합관제",
    "관제센터",
    "영상관제",
    "영상보안",
    "영상분석",
    "출입통제",
    "물리보안",
    "시설 보안",
    "시설 관제",
    "방범카메라",
    "방범 카메라",
    "보안카메라",
    "보안 카메라",
    "이상행동 감지",
    "침입감지",
    "침입 감지",
    "화재감지 cctv",
    "화재 감지 cctv",
]

SECURITY_CYBER_ONLY_KEYWORDS = [
    "사이버보안",
    "사이버 보안",
    "정보보호",
    "개인정보보호",
    "개인정보 보호",
    "랜섬웨어",
    "악성코드",
    "피싱",
    "제로트러스트",
    "제로 트러스트",
    "클라우드 보안",
    "네트워크 보안",
    "보안 취약점",
]

GENERAL_DISASTER_KEYWORDS = [
    "참사",
    "수해복구",
    "우기",
    "호우",
    "침수",
    "재난복구",
    "안전행정",
    "특별관리",
    "우기",
    "수해복구",
    "호우",
    "폭우",
    "침수",
    "특별관리",
]

GOVERNMENT_ACTORS = [
    "정부",
    "국토교통부",
    "과학기술정보통신부",
    "행정안전부",
    "행안부",
    "경찰청",
    "지자체",
    "지방자치단체",
    "서울시",
    "경기도",
    "공공기관",
    "중기부",
    "중소벤처기업부",
]

GOVERNMENT_ACTIONS = [
    "추진",
    "착수",
    "선정",
    "공모",
    "구축",
    "도입",
    "확대",
    "발표",
    "시행",
    "개정",
    "지원",
    "투입",
    "조성",
    "실증",
    "사업",
    "정책",
    "규제",
    "입찰",
]

COMPANY_REGISTRATION_PATTERNS = [
    "나라장터 등록",
    "조달청 등록",
    "공공 시장 공략",
    "공공시장 공략",
]

COMPANY_GOVERNMENT_PR_KEYWORDS = [
    "수상",
    "표창",
    "장관상",
    "대통령상",
    "국무총리상",
    "인증",
    "지정",
    "등록",
    "선정",
    "획득",
    "수여",
    "우수기업",
    "혁신제품",
    "조달우수제품",
    "벤처나라",
    "나라장터",
]

COMPANY_GOVERNMENT_BUSINESS_KEYWORDS = [
    "수주",
    "따냈",
    "낙찰",
    "계약 체결",
    "공급 계약",
    "사업자로 선정",
    "사업자 선정",
    "운영사로 선정",
    "운영사 선정",
    "공급사로 선정",
    "공급사 선정",
]

ADDITIONAL_CATEGORY_KEYWORDS = {
    CATEGORY_INNODEP: [
        "이노뎁",
        "innodep",
    ],
    CATEGORY_SECURITY: [
        "물리보안",
        "영상보안",
        "영상분석",
        "통합관제",
        "영상관제",
        "관제센터",
        "CCTV",
        "VMS",
        "NVR",
        "방범카메라",
        "보안카메라",
        "출입통제",
        "이상행동 감지",
    ],
    CATEGORY_INDUSTRY: [
        "온디바이스 AI",
        "엣지 AI",
        "피지컬 AI",
        "에이전틱 AI",
        "AI 에이전트",
        "AI 반도체",
        "AI 가속기",
        "AI 인프라",
        "AI 데이터센터",
        "스마트시티",
        "지능형교통",
        "지능형 교통",
        "스마트팩토리",
        "스마트 팩토리",
        "영상분석",
        "통합관제",
        "자율주행",
        "로봇",
        "휴머노이드",
        "컴퓨터비전",
        "디지털트윈",
        "출시",
        "상용화",
        "도입",
        "구축",
        "공급",
        "수주",
        "실증",
        "제휴",
        "협력",
    ],
    CATEGORY_GOVERNMENT: [
        "정부",
        "공공",
        "행정안전부",
        "과학기술정보통신부",
        "과기정통부",
        "조달청",
        "경찰청",
        "서울시",
        "경기도",
        "지자체",
        "공공기관",
        "디지털플랫폼정부",
        "공공데이터",
        "스마트시티",
        "AI",
        "인공지능",
        "디지털",
        "데이터",
        "보안",
        "사이버",
        "CCTV",
        "통합관제",
        "영상분석",
        "국토부",
        "교통",
        "AI 지원",
        "공공조달",
    ],
    CATEGORY_VENTURE: [
        "스타트업",
        "벤처",
        "투자유치",
        "펀드",
        "VC",
        "IPO",
        "창업",
        "상장",
        "유니콘",
        "딥테크",
        "모태펀드",
    ],
    CATEGORY_LABOR: [
        "최저임금",
        "임금",
        "노사",
        "근로시간",
        "고용",
        "일자리",
        "업종별",
        "인상",
        "시급",
        "소상공인",
    ],
}

GOVERNMENT_ACTOR_ALIASES = [
    "정부",
    "행정안전부",
    "과학기술정보통신부",
    "과기정통부",
    "국토교통부",
    "국토부",
    "경찰청",
    "개인정보보호위원회",
    "개보위",
    "KISA",
    "한국인터넷진흥원",
    "서울시",
    "서울특별시",
    "경기도",
    "인천시",
    "부산시",
    "대구시",
    "광주시",
    "대전시",
    "울산시",
    "세종시",
    "지자체",
    "지방자치단체",
    "공공기관",
    "중기부",
    "중소벤처기업부",
]

GOVERNMENT_ACTION_ALIASES = [
    "추진",
    "착수",
    "선정",
    "공모",
    "구축",
    "도입",
    "발표",
    "시행",
    "개정",
    "지원",
    "사업",
    "실증",
    "강화",
    "확대",
    "연결",
    "전환",
    "활용",
]

GOVERNMENT_PRIORITY_DOMAINS = [
    "AI",
    "인공지능",
    "디지털",
    "데이터",
    "데이터·AI",
    "공공데이터",
    "행정데이터",
    "디지털플랫폼정부",
    "디지털 전환",
    "보안",
    "사이버",
    "정보보호",
    "개인정보",
    "개인정보보호",
    "CCTV",
    "통합관제",
    "영상분석",
    "스마트시티",
    "스마트도시",
    "클라우드",
    "플랫폼",
    "도로교통도 AI",
    "AI·디지털",
    "창업",
]

GOVERNMENT_REQUIRED_TOPICS = [
    "AI",
    "인공지능",
    "생성형 AI",
    "데이터",
    "공공데이터",
    "행정데이터",
    "데이터 개방",
    "데이터·AI",
    "빅데이터",
    "디지털",
    "디지털 전환",
    "디지털플랫폼정부",
    "정보화",
    "보안",
    "사이버",
    "정보보호",
    "개인정보",
    "개인정보보호",
    "AI 윤리",
    "윤리 가이드라인",
    "가이드라인",
    "인공지능 기본법",
    "스마트시티",
    "스마트도시",
    "스마트 행정",
    "공공 AI",
    "AI 예산",
    "클라우드",
    "CCTV",
    "통합관제",
    "영상분석",
]

GOVERNMENT_GENERAL_NOISE_KEYWORDS = [
    "공약",
    "수해복구",
    "우기",
    "호우",
    "특별관리",
    "건설행정",
    "불법하도급",
    "입찰관리",
    "공정조사",
]

VENTURE_CORE_KEYWORDS = [
    "스타트업",
    "벤처",
    "벤처기업",
    "창업",
    "창업기업",
    "창업진흥원",
    "중기부",
    "중소벤처기업부",
    "도약 프로그램",
    "스케일업",
    "액셀러레이터",
    "엑셀러레이터",
    "투자유치",
    "투자 유치",
    "시리즈A",
    "시리즈B",
    "시드투자",
    "프리A",
    "프리IPO",
    "VC",
    "벤처캐피탈",
    "벤처 캐피탈",
    "TIPS",
    "팁스",
    "딥테크",
    "기술특례",
    "기술특례상장",
    "모태펀드",
    "한국벤처투자",
    "KVIC",
    "유니콘",
    "예비유니콘",
    "startup",
    "venture",
    "funding",
    "seed round",
    "series a",
    "series b",
    "pre-a",
    "pre-ipo",
]

VENTURE_WEAK_KEYWORDS = [
    "투자",
    "금융",
    "펀드",
    "지원",
    "육성",
    "선정",
    "확보",
    "investment",
    "finance",
    "fund",
]

VENTURE_NOISE_KEYWORDS = [
    "부동산",
    "아파트",
    "분양",
    "주택",
    "건설",
    "대출",
    "금리",
    "예금",
    "적금",
    "보험",
    "증시",
    "주가",
    "테마주",
    "실적",
    "배당",
    "공시",
    "부채",
    "채권",
    "환율",
    "가상자산",
    "코인",
]

INDUSTRY_STRONG_TOPIC_KEYWORDS = [
    "온디바이스 AI",
    "엣지 AI",
    "엣지 컴퓨팅",
    "피지컬 AI",
    "에이전틱 AI",
    "AI 에이전트",
    "AI 반도체",
    "AI 가속기",
    "AI 칩",
    "NPU",
    "GPU",
    "AI 인프라",
    "AI 데이터센터",
    "AI 데이터 센터",
    "컴퓨터비전",
    "컴퓨터 비전",
    "영상분석",
    "영상 분석",
    "스마트시티",
    "스마트 시티",
    "지능형교통",
    "지능형 교통",
    "교통기술",
    "교통 기술",
    "스마트팩토리",
    "스마트 팩토리",
    "디지털트윈",
    "디지털 트윈",
    "로봇",
    "휴머노이드",
    "자율주행",
    "SDV",
]

INDUSTRY_GENERIC_TECH_KEYWORDS = [
    "AI",
    "인공지능",
    "생성형 AI",
    "오픈AI",
    "OpenAI",
    "챗GPT",
    "ChatGPT",
    "제미나이",
    "Gemini",
    "클라우드",
]

INDUSTRY_BUSINESS_ACTION_KEYWORDS = [
    "출시",
    "공개",
    "선보",
    "개발",
    "상용화",
    "도입",
    "구축",
    "공급",
    "수주",
    "계약",
    "협약",
    "제휴",
    "협력",
    "동맹",
    "인수",
    "합병",
    "통합",
    "투자",
    "진출",
    "확장",
    "전환",
    "실증",
    "적용",
    "탑재",
    "운영",
    "생산",
    "매출",
    "시장",
    "전략",
    "경쟁",
    "규제",
    "소송",
]

INDUSTRY_NOISE_KEYWORDS = [
    "AI 충격",
    "AI 위험",
    "AI 우려",
    "AI 경고",
    "충격 대비",
    "대비해야",
    "행동해야",
    "장애 청소년",
    "장애청소년",
    "청소년",
    "취업 지원",
    "취업 돕",
    "인재 양성",
    "인재양성",
    "교육 과정",
    "교육센터",
    "스터디 지원",
    "경진대회",
    "챌린지",
    "봉사",
    "기부",
    "성·마약",
    "성ㆍ마약",
    "마약 질문",
    "음란물",
]

GOVERNMENT_NOISE_ALLOWED_TOPICS = [
    "AI",
    "인공지능",
    "데이터",
    "디지털",
    "스마트시티",
    "스마트도시",
    "보안",
    "CCTV",
    "통합관제",
]

GOVERNMENT_PUBLIC_ACTOR_KEYWORDS = [
    "정부",
    "공공",
    "지자체",
    "지방자치단체",
    "공공기관",
    "과기정통부",
    "과학기술정보통신부",
    "행정안전부",
    "국토교통부",
    "국토부",
    "산업통상자원부",
    "산업부",
    "중기부",
    "중소벤처기업부",
    "경찰청",
    "소방청",
    "서울시",
    "경기도",
    "부산시",
    "대구시",
    "인천시",
    "광주시",
    "대전시",
    "울산시",
    "세종시",
]

GOVERNMENT_PRIMARY_KEYWORDS = [
    "정부",
    "공공",
    "지자체",
    "국책과제",
]

GOVERNMENT_SECONDARY_KEYWORDS = [
    "공공조달",
    "나라장터",
    "통합관제센터",
    "통합관제",
    "행정 AI",
    "AI 행정",
    "스마트시티",
    "스마트도시",
]

GOVERNMENT_COMPANY_RELEVANT_KEYWORDS = [
    "통합관제센터",
    "스마트시티 실증",
    "AI 행정",
    "행정 AI",
    "공공 CCTV",
    "CCTV",
    "재난안전",
    "도시안전",
    "교통체계",
    "ITS",
    "지자체 AI 사업",
    "공공조달",
    "국책과제",
    "영상분석",
]

GOVERNMENT_PROGRAM_KEYWORDS = [
    "디지털플랫폼정부",
    "공공데이터",
    "데이터 개방",
    "데이터개방",
    "공모사업",
    "국책과제",
    "공공혁신 과제",
    "혁신 과제",
    "도약 프로그램",
    "R&D",
    "규제샌드박스",
    "공공조달",
    "나라장터",
    "공공기관",
    "시범사업",
    "스마트시티",
    "스마트도시",
    "도시안전",
    "재난안전",
    "교통체계",
    "ITS",
    "통합관제센터",
    "통합관제",
]

GOVERNMENT_TECH_POLICY_KEYWORDS = [
    "AI",
    "인공지능",
    "데이터",
    "디지털",
    "행정 AI",
    "AI 행정",
    "공공데이터",
    "데이터 개방",
    "디지털플랫폼정부",
    "스마트시티",
    "스마트도시",
    "영상분석",
    "CCTV",
    "통합관제",
]

GOVERNMENT_EXCLUDE_KEYWORDS = [
    "정당 공방",
    "여야 공방",
    "선거",
    "여론조사",
    "인사 논란",
    "인사청문",
    "사건사고",
    "사고 단신",
    "복지 민원",
    "민원",
]

GOVERNMENT_NORMAL_ACTION_KEYWORDS = [
    "추진",
    "착수",
    "선정",
    "공모",
    "구축",
    "도입",
    "발표",
    "시행",
    "개정",
    "지원",
    "사업",
    "실증",
    "강화",
    "확대",
    "전환",
    "활용",
    "개방",
    "정비",
    "제정",
    "책정",
]

INDUSTRY_COMPANY_ALIASES = {
    "네이버": ["네이버", "NAVER"],
    "카카오": ["카카오", "Kakao"],
    "삼성전자": ["삼성전자", "삼성"],
    "LG CNS": ["LG CNS", "엘지씨엔에스"],
    "SK텔레콤": ["SK텔레콤", "SKT"],
    "KT": ["KT", "케이티"],
    "현대차": ["현대차", "현대자동차"],
    "엔비디아": ["엔비디아", "NVIDIA"],
    "마이크로소프트": ["마이크로소프트", "MS", "Microsoft"],
    "오픈AI": ["오픈AI", "OpenAI"],
    "구글": ["구글", "Google"],
    "아마존": ["아마존", "AWS", "Amazon"],
    "메타": ["메타", "Meta"],
    "애플": ["애플", "Apple"],
}

MAX_INDUSTRY_ARTICLES_PER_COMPANY = 1

SOURCE_SCORES = {
    "전자신문": 0.95,
    "보안뉴스": 0.95,
    "ZDNet Korea": 0.9,
    "지디넷코리아": 0.9,
    "디지털데일리": 0.88,
    "블로터": 0.82,
    "테크월드": 0.8,
    "연합뉴스": 0.85,
    "뉴스1": 0.78,
    "뉴시스": 0.78,
    "매일경제": 0.75,
    "한국경제": 0.75,
    "서울경제": 0.75,
    "이데일리": 0.72,
    "머니투데이": 0.72,
    "파이낸셜뉴스": 0.7,
    "조선비즈": 0.72,
    "브릿지경제": 0.68,
}

IMPORTANT_ENTITIES = INNODEP_ENTITIES


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
    minimum: int,
    maximum: int,
    threshold: float,
) -> int:
    """카테고리별 최소/최대 범위 안에서 실제로 몇 개를 뽑을지 결정합니다."""
    if maximum <= 0 or not candidates:
        return 0
    candidate_count = len(candidates)
    strong_threshold = min(1.0, threshold + 0.08)
    strong_count = sum(1 for _, score, _ in candidates if score >= strong_threshold)
    if strong_count >= maximum:
        return maximum
    if strong_count >= minimum:
        return min(maximum, strong_count)
    return min(maximum, candidate_count, minimum)


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
    from .filters import normalize_url

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
        minimum, maximum = category_ranges.get(category, (0, 0))
        target_count = target_count_for_category(
            scored_by_category[category],
            minimum=minimum,
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

    if len(selected) < max_articles:
        best_by_article: dict[str, tuple[str, Article, float, dict[str, float]]] = {}
        for category, article, score, components in all_scored:
            _, maximum = category_ranges.get(category, (0, 0))
            if selected_counts.get(category, 0) >= maximum:
                continue
            if not is_eligible_category_candidate(article, category, score, components, threshold):
                continue
            key = article.canonical_url
            existing = best_by_article.get(key)
            if existing is None or score > existing[2]:
                best_by_article[key] = (category, article, score, components)
        fill_candidates = sorted(best_by_article.values(), key=lambda item: (-item[2], item[1].pub_date))
        for category, article, score, components in fill_candidates:
            if len(selected) >= max_articles:
                break
            if article.canonical_url in selected_urls:
                continue
            if is_similar_to_selected(article, selected):
                continue
            if category == CATEGORY_INDUSTRY:
                company = industry_company_key(article)
                if company and company in selected_industry_companies:
                    continue
            _, maximum = category_ranges.get(category, (0, 0))
            if selected_counts.get(category, 0) >= maximum:
                continue
            selected.append(
                replace(
                    article,
                    score=round(score, 4),
                    category=category,
                    reason=reason_for(article, category, components),
                )
            )
            selected_urls.add(article.canonical_url)
            if category == CATEGORY_INDUSTRY:
                company = industry_company_key(article)
                if company:
                    selected_industry_companies.add(company)
            selected_counts[category] = selected_counts.get(category, 0) + 1

    return selected[:max_articles]
