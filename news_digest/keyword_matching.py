from __future__ import annotations


def keyword_matches_text(text: str, keyword: str) -> bool:
    """단일어는 부분 문자열로, 공백 복합어는 모든 구성어 포함으로 판정합니다."""
    folded_text = text.casefold()
    terms = keyword.casefold().split()
    if not terms:
        return False
    if len(terms) == 1:
        return terms[0] in folded_text
    return all(term in folded_text for term in terms)
