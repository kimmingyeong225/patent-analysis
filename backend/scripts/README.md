# backend/scripts

일회성 프로브/디버깅 스크립트 모음. 프로덕션 런타임 경로가 아님.

## cleanup_fake_similarity.py

Phase 1-F 이전 생성된 **legacy 가짜 `similarity_score`** (rank-based `0.95 / 0.90 / 0.85 ...` 고정값)를 DB `search_results` 테이블에서 탐지하는 진단 스크립트. **dry-run 전용**(실제 수정은 하지 않음).

### 배경

Phase 1-F 이전 `kipris.parse_kipris_dict_to_json`은 `similarity_score = round(0.95 - idx*0.05, 2)` 를 기본 채워넣었고 FAISS 성공 시 덮어썼다. FAISS가 실패한 검색의 경우 이 가짜 값이 그대로 DB에 저장되어 UI에 노출됐을 수 있다.

### 탐지 방법

- 테이블: `search_results` (patents 테이블엔 similarity_score 없음)
- 조건: `similarity_score == round(0.95 - (rank-1)*0.05, 2)` 페어 매칭
- 오차 허용: `abs(diff) < 1e-9`

### 실행

```bash
python backend/scripts/cleanup_fake_similarity.py
# 또는 명시적으로:
python backend/scripts/cleanup_fake_similarity.py --dry-run
```

### 출력

1. 전체 search_results 행 수 / legacy 매칭 행 수
2. 쿼리별 집계 (어느 검색 세션이 영향받았는지)
3. 상위 20개 샘플 (query / rank / patent_id / score)
4. 권장 정리 SQL 가이드 (사용자가 수동 실행 판단)

### 주의

- `--apply` 는 의도적으로 미구현. 실제 정리 전 사용자가 샘플 확인 후 수동 SQL 실행.
- 신규 저장(Phase 1-F 이후)은 `similarity_score=0.0` 로 시작 후 FAISS 덮어쓰므로 점진적으로 영향 감소.

## probe_detail_api.py

KIPRIS 서지상세조회 API(`getBibliographyDetailInfoSearch`)의 실제 응답 구조를 확인하는 프로브. 새 필드 추가 또는 API 스펙 변경 조사 시 사용.

### 실행

```bash
# 기본 샘플 번호로 실행 (KIPRIS_API_KEY .env 필요)
python backend/scripts/probe_detail_api.py

# 특정 출원번호로 실행
python backend/scripts/probe_detail_api.py 1020230012345
```

### 출력

1. HTTP 상태/길이
2. 원문 XML 앞 2000자 (태그명 직관적 확인)
3. xmltodict 파싱 dict 전체 (`pprint`)

### 주의

- URL 베이스가 freeSearch와 다름: `/kipo-api/kipi/...` (freeSearch는 `/openapi/rest/...`)
- API 키 필드명이 다름: `ServiceKey` (freeSearch는 `accessKey`, 대소문자 주의)
- 무료 쿼터를 소모하므로 반복 실행 자제
