# backend/scripts

일회성 프로브/디버깅 스크립트 모음. 프로덕션 런타임 경로가 아님.

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
