from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from math import sqrt
import re


def tokens(text: str) -> list[str]:
    """추천 유사도 계산에 사용할 단어 토큰을 뽑습니다."""
    return re.findall(r"[0-9A-Za-z가-힣]+", text.casefold())


def char_ngrams(text: str, size: int = 2) -> list[str]:
    """짧은 한국어 표현도 비교되도록 글자 단위 n-gram을 만듭니다."""
    compact = re.sub(r"\s+", "", text.casefold())
    if len(compact) <= size:
        return [compact] if compact else []
    return [compact[index : index + size] for index in range(len(compact) - size + 1)]


def lexical_cosine(left: str, right: str) -> float:
    """추천 다양성 계산에 사용하는 가벼운 텍스트 유사도입니다."""
    left_terms = tokens(left) + char_ngrams(left)
    right_terms = tokens(right) + char_ngrams(right)
    if not left_terms or not right_terms:
        return 0.0
    left_counts = Counter(left_terms)
    right_counts = Counter(right_terms)
    dot = sum(count * right_counts.get(term, 0) for term, count in left_counts.items())
    left_norm = sqrt(sum(count * count for count in left_counts.values()))
    right_norm = sqrt(sum(count * count for count in right_counts.values()))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def title_similarity(left: str, right: str) -> float:
    """중복 기사 판정에 쓰는 제목 유사도입니다."""
    normalized_left = " ".join(tokens(left))
    normalized_right = " ".join(tokens(right))
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()
