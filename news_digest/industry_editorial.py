from __future__ import annotations

from dataclasses import dataclass
import re

from .keyword_matching import keyword_matches_text
from .models import Article


INDUSTRY_INTENTS = {
    "model_platform": "모델·플랫폼·빅테크",
    "semiconductor_infra": "반도체·인프라",
    "enterprise_adoption": "기업 도입·업무 혁신",
    "physical_manufacturing": "제조·로봇·피지컬 AI",
    "vertical_applications": "산업별 응용",
    "market_supply_chain": "시장·경쟁·공급망",
    "regulation_social": "규제·안전·사회 영향",
}

INDUSTRY_INTENT_QUERIES = {
    "model_platform": ["생성형 AI", "AI 모델", "AI 플랫폼", "AI 에이전트"],
    "semiconductor_infra": ["AI 반도체", "GPU AI", "AI 데이터센터", "AI 인프라"],
    "enterprise_adoption": ["기업 AI", "업무 AI", "산업 AX"],
    "physical_manufacturing": ["피지컬 AI", "AI 로봇", "스마트팩토리 AI", "자율주행 AI"],
    "vertical_applications": ["의료 AI", "바이오 AI", "국방 AI", "교육 AI"],
    "market_supply_chain": ["AI 시장", "AI 경쟁", "AI 공급망"],
    "regulation_social": ["AI 규제", "AI 안전", "AI 저작권", "AI 일자리"],
}

QUERY_TO_INTENT = {
    query.casefold(): intent
    for intent, queries in INDUSTRY_INTENT_QUERIES.items()
    for query in queries
}

INTENT_KEYWORDS = {
    "model_platform": [
        "생성형 AI", "AI 모델", "거대언어모델", "LLM", "파운데이션 모델",
        "AI 플랫폼", "AI 에이전트", "에이전틱 AI", "챗GPT", "제미나이",
        "클로드", "오픈AI", "앤트로픽", "구글", "마이크로소프트", "메타",
        "온디바이스 AI", "AI 이미지", "이미지 생성", "음성 합성",
    ],
    "semiconductor_infra": [
        "AI 반도체", "AI 칩", "GPU", "NPU", "HBM", "AI 가속기",
        "AI 인프라", "AI 데이터센터", "AI 데이터 센터", "클라우드",
    ],
    "enterprise_adoption": [
        "기업 AI", "업무 AI", "업무 혁신", "AX", "AI 전환", "AI 도입",
        "AI 활용", "업무 자동화", "AI 솔루션", "AI 서비스",
    ],
    "physical_manufacturing": [
        "피지컬 AI", "로봇", "휴머노이드", "스마트팩토리", "스마트 팩토리",
        "자율주행", "SDV", "디지털트윈", "디지털 트윈", "제조 AI",
        "컴퓨터비전", "영상분석",
    ],
    "vertical_applications": [
        "의료 AI", "헬스케어 AI", "바이오 AI", "신약 AI", "금융 AI",
        "교육 AI", "AI 교육", "인재 양성", "국방 AI", "농업 AI", "법률 AI",
        "콘텐츠 AI",
    ],
    "market_supply_chain": [
        "AI 시장", "시장 점유율", "AI 경쟁", "AI 생태계", "공급망",
        "수출 규제", "M&A", "인수합병", "매출", "투자 계획", "생태계",
    ],
    "regulation_social": [
        "AI 규제", "AI 기본법", "AI 안전", "인공지능법", "저작권",
        "저작물", "무단 사용", "집단소송", "규제", "법 제정", "AI 정책",
        "개인정보", "딥페이크", "일자리", "고용 충격", "윤리", "책임 AI",
    ],
}

AI_DIRECT_KEYWORDS = [
    "AI", "인공지능", "생성형 AI", "거대언어모델", "LLM", "챗GPT",
    "ChatGPT", "제미나이", "Gemini", "클로드", "Claude", "오픈AI",
    "OpenAI", "머신러닝", "딥러닝",
]

AI_NATIVE_TECH_KEYWORDS = [
    "AI 반도체", "GPU", "NPU", "온디바이스", "피지컬 AI", "AI 에이전트",
    "에이전틱 AI", "컴퓨터비전", "자율주행", "휴머노이드", "스마트팩토리",
    "영상분석", "AI 데이터센터",
]

IMPORTANCE_KEYWORDS = [
    "세계 최초", "국내 최초", "상용화", "출시", "공개", "도입", "구축",
    "투자", "인수", "합병", "수주", "공급", "계약", "표준", "규제",
    "법안", "법 제정", "신설", "저작권", "소송", "정책", "시장", "점유율",
    "매출", "생산", "수출", "실증", "개발", "확대", "전환", "협력", "제휴",
]

PROMOTIONAL_KEYWORDS = [
    "홍보대사", "브랜드 대상", "고객 감사", "이벤트", "캠페인", "체험단",
    "무료 증정", "기념 행사", "세미나 개최", "웨비나", "부스 운영",
    "우수기업 선정", "수상", "인증 획득", "업무협약", "MOU",
]

PROMOTIONAL_HARD_KEYWORDS = [
    "지원사업 선정", "컨소시엄 선정", "업무협약", "MOU", "수상", "인증 획득",
    "브랜드 대상", "체험단", "이벤트",
]

EDITORIAL_MIN_CENTRALITY = 0.60
EDITORIAL_MIN_IMPORTANCE = 0.30
EDITORIAL_MIN_INTENT = 0.38


@dataclass(frozen=True)
class IndustryEditorialAssessment:
    centrality: float
    importance: float
    promotionality: float
    intent: str
    intent_label: str
    intent_score: float
    editorial_score: float
    intent_scores: dict[str, float]


def _has(text: str, keyword: str) -> bool:
    return keyword_matches_text(text, keyword)


def _coverage(text: str, keywords: list[str], limit: int) -> float:
    matches = sum(_has(text, keyword) for keyword in keywords)
    return min(1.0, matches / max(1, limit))


def lexical_intent_scores(article: Article) -> dict[str, float]:
    title = article.title
    description = article.description
    scores: dict[str, float] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        title_score = _coverage(title, keywords, 2)
        description_score = _coverage(description, keywords, 3)
        scores[intent] = min(1.0, 0.65 * title_score + 0.35 * description_score)
    return scores


def ai_centrality_score(article: Article, semantic_relevance: float) -> float:
    title_direct = _coverage(article.title, AI_DIRECT_KEYWORDS, 1)
    body_direct = _coverage(article.description, AI_DIRECT_KEYWORDS, 1)
    native_title = _coverage(article.title, AI_NATIVE_TECH_KEYWORDS, 1)
    native_body = _coverage(article.description, AI_NATIVE_TECH_KEYWORDS, 1)
    title_signal = max(title_direct, 0.82 * native_title)
    body_signal = max(0.55 * body_direct, 0.45 * native_body)
    lexical = max(
        title_signal,
        body_signal,
    )
    semantic = max(0.0, min(1.0, (semantic_relevance - 0.48) / 0.32))
    combined = max(lexical, 0.70 * lexical + 0.30 * semantic)
    if title_signal == 0.0:
        combined = min(combined, 0.55)
    return round(combined, 4)


def industry_importance_score(article: Article) -> float:
    text = f"{article.title} {article.description}"
    action = _coverage(text, IMPORTANCE_KEYWORDS, 2)
    specificity = _coverage(text, AI_NATIVE_TECH_KEYWORDS, 2)
    quantified = 1.0 if re.search(r"(?:\d[\d,.]*\s*(?:억|조|만|%|배|대|개|명|건)|\d{4}년)", text) else 0.0
    named_actor = 1.0 if re.search(r"(?:[가-힣A-Za-z0-9]{2,20})(?:,|·|은|는|이|가)\s", article.title) else 0.0
    return round(min(1.0, 0.45 * action + 0.25 * specificity + 0.20 * quantified + 0.10 * named_actor), 4)


def promotionality_score(article: Article) -> float:
    text = f"{article.title} {article.description}"
    promo = _coverage(text, PROMOTIONAL_KEYWORDS, 2)
    low_information_title = 1.0 if len(re.findall(r"[가-힣A-Za-z0-9]+", article.title)) <= 4 else 0.0
    hard_promo = 1.0 if any(_has(article.title, keyword) for keyword in PROMOTIONAL_HARD_KEYWORDS) else 0.0
    return round(
        min(1.0, max(0.85 * hard_promo, 0.85 * promo + 0.15 * low_information_title)),
        4,
    )


def assess_industry_article(
    article: Article,
    *,
    semantic_relevance: float,
    semantic_intent_scores: dict[str, float] | None = None,
) -> IndustryEditorialAssessment:
    lexical_scores = lexical_intent_scores(article)
    semantic_scores = semantic_intent_scores or {}
    query_intent = QUERY_TO_INTENT.get(article.query.strip().casefold())
    intent_scores: dict[str, float] = {}
    for intent in INDUSTRY_INTENTS:
        lexical = lexical_scores[intent]
        semantic = max(0.0, min(1.0, semantic_scores.get(intent, 0.0)))
        combined = 0.55 * semantic + 0.45 * lexical if semantic_scores else lexical
        if query_intent == intent:
            # 넓은 검색 결과를 그대로 믿지는 않되, 해당 편집 의도로 수집된
            # 사실이 과거 데이터의 묶음 편향을 교정할 만큼은 반영되게 합니다.
            combined = max(combined, 0.55 * semantic + 0.25)
        if lexical >= 0.35 and lexical == max(lexical_scores.values()):
            combined += 0.20
        intent_scores[intent] = round(min(1.0, combined), 4)
    intent = max(intent_scores, key=intent_scores.get)
    intent_score = intent_scores[intent]
    centrality = ai_centrality_score(article, semantic_relevance)
    importance = industry_importance_score(article)
    promotionality = promotionality_score(article)
    editorial_score = max(
        0.0,
        min(1.0, 0.40 * centrality + 0.35 * importance + 0.25 * intent_score - 0.15 * promotionality),
    )
    return IndustryEditorialAssessment(
        centrality=centrality,
        importance=importance,
        promotionality=promotionality,
        intent=intent,
        intent_label=INDUSTRY_INTENTS[intent],
        intent_score=intent_score,
        editorial_score=round(editorial_score, 4),
        intent_scores=intent_scores,
    )


def editorial_rejection_reasons(assessment: IndustryEditorialAssessment) -> list[str]:
    reasons: list[str] = []
    if assessment.centrality < EDITORIAL_MIN_CENTRALITY:
        reasons.append("AI 중심성 부족")
    if assessment.importance < EDITORIAL_MIN_IMPORTANCE:
        reasons.append("산업 중요도 부족")
    if assessment.intent_score < EDITORIAL_MIN_INTENT:
        reasons.append("편집 의도 불명확")
    if assessment.promotionality >= 0.72 and assessment.importance < 0.58:
        reasons.append("홍보성 대비 정보량 부족")
    return reasons
