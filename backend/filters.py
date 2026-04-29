"""검색 결과 필터 — 출원연도 / 법적상태 공통 적용.

main.py (_apply_filters → apply_filters) / crud.py (_apply_cache_filters
삭제) 에서 동일 로직 중복이었던 것을 단일 모듈로 통합 (Phase 2-A.3).
"""
import schemas


def apply_filters(patents: list, request: schemas.SearchRequest) -> list:
    """출원연도 범위, 법적상태 필터를 적용합니다."""
    filtered = patents

    # 출원연도 필터
    if request.year_from or request.year_to:
        def in_year_range(p):
            date = p.get("공개등록공보", {}).get("application_date", "") or ""
            if len(date) < 4:
                return False
            try:
                year = int(date[:4])
            except ValueError:
                return False
            if request.year_from and year < request.year_from:
                return False
            if request.year_to and year > request.year_to:
                return False
            return True
        filtered = [p for p in filtered if in_year_range(p)]

    # 법적상태 필터
    if request.status:
        filtered = [
            p for p in filtered
            if p.get("법적상태", {}).get("status", "") == request.status
        ]

    return filtered
