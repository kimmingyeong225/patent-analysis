# 핸드오프 — Phase 2-C 종료 시점 (2026-05-17)

본 핸드오프는 Phase 2-A (백엔드, 이전 세션) + Phase 2-C (프론트엔드, 본 세션) 통합 결산 + Phase 3 진입 준비 문서입니다.

> **참고**: 명시된 `handoff_after_phase2a.md` 파일은 본 환경에서 찾지 못함 (project / memory / .claude 디렉토리 모두 검색 0건). Phase 2-A 결산은 git log + memory + 본 세션 대화 기반으로 재구성.

---

## 1. 본 세션 결산 (Phase 2-A + Phase 2-C 통합)

### Phase 2-A (백엔드, 이전 세션, 4 커밋)

| Phase | commit | 제목 | 핵심 |
|---|---|---|---|
| 2-A.1 | `5328687` | fix(trend): skip caching empty results | `_trend_cache` 가 빈 결과 캐싱 → 백엔드 일시 장애 시 stale empty 영구화. 빈 결과는 skip |
| 2-A.2 | `52943fb` | fix(faiss): cache key includes patents id hash | FAISS index 캐시 키가 query 만 사용 → 같은 query 다른 patents set 시 stale index. patents id hash 포함 |
| 2-A.3 | `63d4189` | refactor(filters): extract apply_filters | `_apply_filters` / `_apply_cache_filters` 라인 단위 중복 → `backend/app/services/filters.py` 분리 |
| 2-A.4 | `f5058bc` | perf(crud): batch SELECT and bulk INSERT | `save_search_results` N+1 SELECT → batch SELECT IN + `bulk_insert_mappings`, 쿼리 63% 감소 |

**Phase 2-A 잔여**: ① `/similarity` 캐시 + LLM 호출 비용 최적화 (Phase 3-D 후보로 이관)

### Phase 2-C (프론트엔드, 본 세션, 5 commit + 1 skip + 1 보류)

| Phase | commit | 제목 | 핵심 | STEP 4 (수동 가이드) |
|---|---|---|---|---|
| 2-C.1 | — (skip) | StickyHeader stale 입력값 | **false positive 확정** — `setQuery` → `setView("loading")` → ResultView unmount/remount → 새 SearchBar 가 새 initialValue 초기화 흐름 검증. STEP 2 §3 추적 결과 | N/A |
| 2-C.2 | `5fe6f6a` | fix(trend): abort in-flight requests | `TrendChart.fetchTrend` AbortController 미적용. 6 가드 (ref / 사전 abort / 신규 controller / signal / 응답 후 / catch silent / finally / useEffect cleanup) + `useCallback([])` 안정화 | `.tmp_phase2c2_step4_manual.md` |
| 2-C.3 | `e19decc` | fix(search): abort in-flight requests | `page.tsx.handleSearch` 가 `fetchPatents` 호출 시 signal 미전달. 시나리오 A (race) + B (handleHome → GPT-4o 비용 낭비) 동시 해결 | `.tmp_phase2c3_step4_manual.md` |
| 2-C.4 | `997b98e` | refactor(frontend): remove unreachable mock branch | `BACKEND_URL = process.env.X \|\| "fallback"` 으로 항상 truthy → `if (!BACKEND_URL)` 분기 dead code. 5줄 삭제 + `.env.local.example` 주석 catch 폴백 명시. **catch 폴백 보존** (mockPatents / mockAnalysis import 유지) | `.tmp_phase2c4_step4_manual.md` |
| 2-C.5 | `e6dae18` | refactor(frontend): extract buildPatentLinks | `PatentList.tsx:45-53` / `PatentDetailModal.tsx:82-88` 의 KIPRIS / Google Patents URL 빌드 로직 라인 단위 중복 → `frontend/lib/patentUrls.ts` 신규. **순환 의존 회피** (PatentList → Modal 이미 의존, Modal export 옵션 배제) | `.tmp_phase2c5_step4_manual.md` |
| 2-C.6 | **미착수** | a11y (focus trap / tab role / aria-expanded) | PatentDetailModal / AISummaryWidget / FilterPanel 3개 영역. 변경 면적 큼, 수동 검증 부담 | — |
| 2-C.7 | `f4c3ed7` | fix(trend): replace any with TooltipProps | `TrendChart.tsx:17` CustomTooltip 의 명시적 `any` → `TooltipProps<number, string>`. **1차 시도 실패 → 2차 (본문 가드 추가) 통과** 의 실측 가치 입증 — `any` 가 숨기던 `payload[0].value` undefined 가능성 catch. STEP 4 생략 (변경 3줄, tsc+build 통과로 충분) | (생략) |

### chore (1 커밋)
- `92aa1cc` chore: gitignore covers .tmp_* in all subdirs — `**/.tmp_*` 패턴으로 확장 (이전: `backend/.tmp_*` 만 커버)

### 누적 10 커밋 일관성 (feature/ui-llm)
모두 `westjun1021 <tjwns4603@gmail.com>` 동일 author == committer. force / amend / rebase 0건. push origin/feature/ui-llm 동기화 완료.

---

## 2. Phase 2-C 잔여 항목

### #6 a11y (보류)

| 영역 | 파일 | 권장 처치 |
|---|---|---|
| Modal focus trap | `PatentDetailModal.tsx:20-32` | 모달 오픈 시 자동 focus + Tab 키 cycle (수동 focus trap 또는 `focus-trap-react` 도입) |
| Tab role 의미론 | `AISummaryWidget.tsx:166-178` | 5개 탭 `<button>` → `role="tablist"` / `role="tab"` / `aria-selected` 적용 |
| Toggle aria-expanded | `FilterPanel.tsx:47-63` | 토글 버튼에 `aria-expanded` / `aria-controls` 적용 |

- **우선순위**: Med (사용자 영향 비기능적, 접근성 가드)
- **변경 면적**: 큼 (3개 컴포넌트, 분할 가능 — Phase 2-C.6.a / 6.b / 6.c)
- **회귀 위험**: 중 (수동 검증 부담 — 스크린리더 / 키보드 nav 환경 필요)
- **권장**: 별도 Phase (Phase 2-D 또는 Phase 4 등) 또는 접근성 검증 환경 구축 후 진행

진단 보고서: `frontend/.tmp_phase2c_diagnostic.md` (전체 7항목, #6 부분 참조)

---

## 3. STEP 게이트 패턴

본 세션에서 정착된 8-STEP 게이트 (commit 1건당):

| STEP | 작업 | 게이트 |
|---|---|---|
| 1 | 진단 (`.tmp_phaseXX_diagnostic.md` 작성) | 사용자 명시 승인 → STEP 2 |
| 2 | 옵션 합의 + 결정 | AskUserQuestion 또는 사용자 메시지 명시 옵션 |
| 3 | 구현 (코드 변경) + 자가검증 | 13-15 항목 표 보고 |
| 4 | tsc + build + 수동 검증 가이드 (`.tmp_phaseXX_step4_manual.md`) | (생략 가능 시 commit 메시지에 근거 명시) |
| 5-1 | git add + staged diff (`.tmp_phaseXX_staged.diff`) + 자가검증 10항목 | 사용자 명시 승인 → STEP 5-2 |
| 5-2 | commit -F 메시지 파일 경유 (`.tmp_phaseXX_commit_msg.txt`) | 메시지 paste 명시 승인 필요 (미래시제 ≠ 진행 승인) |
| 5-2.b | raw 객체 검증 (`git show ... --no-patch --format=%B` → `.tmp_phaseXX_commit_raw.txt`) + grep 손상 패턴 + byte-level diff + 작성자 일관성 N 커밋 | 사용자 명시 승인 → STEP 5-3 |
| 5-3 | push (사실 확인 → push → 후 확인) | 1회만, force / amend 금지 |

### 본 세션 새 학습 (게이트 정신)

| Phase | 학습 |
|---|---|
| 2-C.1 | **false positive 자가 발견** — STEP 1 진단에서 의심 → STEP 2 합의 중 추적으로 정정. 진단 보고서가 항상 사실이 아닐 수 있음 |
| 2-C.3 | **§3-B 시나리오 추가 발견** — race 만 보다가 handleHome 미취소 시 GPT-4o 호출 비용 낭비 발견. STEP 1 진단에서 광범위 시나리오 검토 가치 |
| 2-C.4 | **사용자 spec 정의 오류 정정** — "5줄 삭제" spec 이 사실은 dead code 제거였지 catch 폴백 제거가 아님. STEP 3 보고에서 spec literal vs 실제 차이 명시 |
| 2-C.4 STEP 3 | **spec literal vs 실제 차이 명시 보고 패턴** 정착 |
| 2-C.7 | **1차 → 2차 시도 학습** — any → strict 타입 전환 시 1차 (시그니처만) tsc 실패 → 2차 (본문 가드 추가) 통과. any 가 숨기던 잠재 런타임 에러 명시 catch 의 실측 가치 |

---

## 4. 본 세션에서 정착된 새 검증 패턴

### Phase 2-A 패턴 (이전 세션 추정)
- byte-level diff (commit 메시지 무결성)
- fixed-string grep (`-F` 옵션, 한글 손상 검출)
- push 사실 확인 (HEAD / origin / log ahead — Phase 2-A.4 학습 의무화)
- SQL 카운터 (bulk_insert_mappings 안전성 검증)
- IN 절 한계 인지 (PostgreSQL 32767 parameter limit 등)

### Phase 2-C 추가 패턴
- **STEP 3 사전 조사 (D)** — 무작정 변경 전 grep 으로 사용처 정확 파악 (Phase 2-C.4 학습, 컴포넌트 catch 폴백 보존 확인)
- **spec literal vs 실제 차이 명시 보고** (Phase 2-C.4 STEP 3 학습)
- **type-only import** (`import type { ... }`) — 런타임 영향 0 검증 (Phase 2-C.7)
- **특수문자 카운트 + 위치 명시** (Phase 2-C.x 누적: `→`, `—`, `↔`, `?.`, `??`, `<>`, `[]`, `||`, `'10'` 등)
- **false positive 의미 분석 분류** — 정상 코드 토큰 (`payload[0].value?.toLocaleString()` 의 `?`) vs 한글 자리 손상 시그니처 구별 (Phase 2-C.7)
- **같은 파일 내 변경 영역 분리** — Phase 2-C.2 (TrendChart fetchTrend L60-97) vs Phase 2-C.7 (TrendChart CustomTooltip L17-23) 영역 무간섭 검증
- **순환 의존 회피** — 옵션 비교 시 의존 방향 분석 (Phase 2-C.5 옵션 a vs b)

---

## 5. .tmp_* 위생 정책

### .gitignore 패턴
- `**/.tmp_*` (commit `92aa1cc`, 이전 `backend/.tmp_*` 만 → 전체 서브디렉토리)

### 정리 정책 (Phase 종료 시)
- **삭제 대상** (commit / push 완료 후):
  - `.tmp_phaseXX_step3.diff` (STEP 3 자가검증 diff)
  - `.tmp_phaseXX_staged.diff` (STEP 5-1 staged diff)
  - `.tmp_phaseXX_commit_msg.txt` (STEP 5-2 commit 메시지 원본)
  - `.tmp_phaseXX_commit_raw.txt` (STEP 5-2.b raw 메시지)
- **유지 대상**:
  - `.tmp_phaseXX_diagnostic.md` (진단 보고서, 다음 Phase 참조 가능)
  - `.tmp_phaseXX_step4_manual.md` (수동 검증 가이드, 사용자 미완 시 후속)
  - `.tmp_phaseX_step2.md` (false positive 학습 사례 등)

### 현재 잔여 (9건)

| 파일 | 의미 |
|---|---|
| `frontend/.tmp_phase2c_diagnostic.md` | 전체 7항목 진단, #6 a11y 미처리 참조 |
| `frontend/.tmp_phase2c1_step2.md` | false positive 학습 사례 (#1 StickyHeader 추적) |
| `frontend/.tmp_phase2c2_diagnostic.md` | Phase 2-C.2 진단 |
| `frontend/.tmp_phase2c2_step4_manual.md` | 수동 검증 미완 |
| `frontend/.tmp_phase2c3_diagnostic.md` | Phase 2-C.3 진단 |
| `frontend/.tmp_phase2c3_step4_manual.md` | 수동 검증 미완 |
| `frontend/.tmp_phase2c4_diagnostic.md` | Phase 2-C.4 진단 |
| `frontend/.tmp_phase2c4_step4_manual.md` | 수동 검증 미완 |
| `frontend/.tmp_phase2c5_step4_manual.md` | 수동 검증 미완 |

수동 검증 미완 4건 (`step4_manual.md`) 은 사용자가 백엔드 실기동 + 브라우저 검증 후 결과 양식 채워야 함.

---

## 6. 보존된 결정 사항

| 결정 | 출처 | 영향 |
|---|---|---|
| 헬퍼 무수정 원칙 (백엔드) | Phase 1-G.1 ~ 2-A.x | filters.py 분리 시에도 helper signature 유지 |
| `filters.py` 분리 패턴 | Phase 2-A.3 (`63d4189`) | **Phase 2-C.5 `patentUrls.ts` 분리에 동형 적용** — 라인 단위 동치 이동 + 단방향 의존 |
| AbortController 6 가드 패턴 | `page.tsx fetchAnalysis` (기존) | **Phase 2-C.2 fetchTrend** + **Phase 2-C.3 fetchPatents** 동형 적용 |
| Mock 사용 정책 | Phase 1-F (Mock 투명화) + Phase 2-C.4 | dead code 제거 (`!BACKEND_URL` 분기) + catch 폴백 보존 (mockPatents / mockAnalysis import 유지) |
| `_trend_cache` per-key Lock 미적용 | Phase 1-G 경계 (memory project_phase_followups.md #1) | 후속 Phase 대상, 본 세션 범위 밖 |
| `_apply_faiss_scores` 첫 요청 chunks 공유 | Phase 1-G (memory #2) | 캐시 정합성 별도 검토 대상 |
| 명시 승인 게이트 엄수 | memory feedback_strict_gates.md | commit 메시지 paste / 미래시제 ≠ 진행 승인. 명시 동사 필수 |

---

## 7. 다음 세션 진입점 — Phase 3 후보

### 사용자 리스트 기준

| Phase 후보 | 설명 | 변경 영역 | 난이도 |
|---|---|---|---|
| **3-A** | 백엔드 구조 정리 — FastAPI APIRouter 도입, 라우터 분리 | `backend/app/` 전반 | 큼 (도메인 정합) |
| **3-B** | DX — Dockerfile + `.env.example` 정비 | root + backend + frontend | 중 |
| **3-C** | 테스트 CI/CD — 프론트 테스트 프레임워크 (Vitest / RTL) + GitHub Actions | 신규 인프라 | 큼 |
| **3-D** | LLM 비용 최적화 (Phase 2-A 잔여 ① `/similarity` 캐시 + LLM 호출 비용) | backend | 중 |

### 추천 순서

1. **3-A 우선** — 백엔드 모듈화 (큰 작업이지만 추후 모든 Phase 의 도메인 정합 확보)
2. **3-B** — DX 인프라 (3-A 의 모듈 구조 위에서 Dockerfile 단순화)
3. **3-C** — 테스트 자동화 (3-A/3-B 후 안정 구조 위에서 CI/CD 추가)
4. **3-D** — 비용 최적화 (위 인프라 위에서)

### 대안
- 사용자 우선순위 자유 선택
- Phase 2-C.6 (#6 a11y) 마저 처리 후 Phase 3 진입
- 다른 영역 (예: 사용자 신규 요구사항)

---

## 8. 다음 세션 시작 시 권장 절차

1. **본 핸드오프 (`handoff_after_phase2c.md`) 첨부** 또는 사용자가 첫 메시지에서 참조 명시
2. **관련 진단 보고서 첨부** (작업 영역에 따라):
   - Phase 3-A/B/C: 백엔드 진단 (이전 세션의 backend `.tmp_phase2a_diagnostic.md` 존재 시)
   - Phase 2-C.6 (a11y) 진행 시: `frontend/.tmp_phase2c_diagnostic.md` #6 참조
3. **다음 작업 명시** — 위 §7 후보 중 또는 사용자 지정
4. **첫 STEP 시작 전 환경 / 브랜치 / git status 확인 1회**:
   - `git status` (clean 기대)
   - `git rev-parse HEAD` / `git rev-parse origin/feature/ui-llm` 일치 확인
   - 새 Phase 명명 결정 (Phase 3-A.1 / Phase 2-C.6.a 등)
5. **첫 STEP 1 진단 보고서 작성 → 사용자 명시 승인 → 다음 STEP**

---

## 9. 누적 커밋 그래프 (feature/ui-llm)

```
f4c3ed7 fix(trend): replace any with TooltipProps [Phase 2-C.7]
e6dae18 refactor(frontend): extract buildPatentLinks [Phase 2-C.5]
997b98e refactor(frontend): remove unreachable mock branch [Phase 2-C.4]
e19decc fix(search): abort in-flight requests [Phase 2-C.3]
5fe6f6a fix(trend): abort in-flight requests [Phase 2-C.2]
92aa1cc chore: gitignore covers .tmp_* in all subdirs
f5058bc perf(crud): batch SELECT and bulk INSERT [Phase 2-A.4]
63d4189 refactor(filters): extract apply_filters [Phase 2-A.3]
52943fb fix(faiss): cache key includes patents id hash [Phase 2-A.2]
5328687 fix(trend): skip caching empty results [Phase 2-A.1]
...
```

- origin/feature/ui-llm 동기화 완료 (`HEAD == origin = f4c3ed7`)
- working tree clean
- 모든 commit author = committer = `westjun1021 <tjwns4603@gmail.com>`
- force / amend / rebase 이력 0건

---

## 10. 협업 원칙

1. **추측 없이 진행** — 코드 상태 / 의도 모호 시 사용자에게 명시 확인. 가정 명시 후 진행 절대 금지.
2. **STEP 게이트 분리** — 각 STEP 종료 후 사용자 명시 승인 대기. 다음 STEP 자동 진행 금지.
3. **코드 변경 / git 명령 명시 범위 외 금지** — 사용자가 명시한 파일 / 변경 / commit 외 작업 금지. 의심 시 사용자 확인.
4. **`.tmp_*` 파일 경유** — 진단 / 가이드 / staged diff / commit 메시지 모두 gitignored 임시 파일 경유. commit 영향 0 보장.
5. **raw 출력 그대로 보고** — git status / diff / log / tsc / build 등 출력 재해석 / 요약 금지. 출력 후 분석 별도.
6. **실패 시 즉시 정지 + 사용자 보고** — tsc / build / push 실패, 예상치 못한 상태, 정합성 위반 모두 즉시 정지.
7. **단일 Phase 단일 commit 원칙** — 한 Phase = 한 의도 = 한 commit. 여러 변경 묶음 금지.
8. **메시지 파일 경유 commit** — 한글 본문 / 줄바꿈 보존 위해 `.tmp_phaseXX_commit_msg.txt` UTF-8 저장 → `git commit -F`. 인라인 `-m` 금지.
9. **force / amend / rebase 명시 승인 없이 금지** — push 후 history 변경 절대 금지.
10. **본 핸드오프 + 협업 원칙은 모든 새 세션에서 재확인** — 새 세션 시작 시 본 파일 첨부 권장.

---

## 부록 A. 본 환경 정보

- **OS**: Windows 11 (Git Bash for shell)
- **Project root**: `C:\dev\patent\patent-analysis`
- **Branch**: `feature/ui-llm`
- **Remote**: `https://github.com/kimmingyeong225/patent-analysis.git`
- **User**: `westjun1021 <tjwns4603@gmail.com>` (git config), `tjwns4603@gmail.com` (system)
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + FAISS + KIPRIS API + OpenAI GPT-4o
- **Frontend**: Next.js ^15.1 (App Router) + React ^19 + TypeScript ^5 strict + Tailwind ^3.4 + recharts ^2.13 + framer-motion ^11.15

## 부록 B. memory 시스템 참조

위치: `C:\Users\tjwns\.claude\projects\C--dev-patent-patent-analysis\memory\`

| 파일 | 의미 |
|---|---|
| `MEMORY.md` | 인덱스 (자동 로드) |
| `feedback_strict_gates.md` | 명시 승인 게이트 엄수 규칙 |
| `project_phase_followups.md` | Phase 1-G 시점 사용자 후속 메모 (2026-04-24, 22일 전 — 검증 후 인용 권장) |

새 세션에서 본 핸드오프 + memory 함께 로드.

---

**핸드오프 작성 완료 시점**: 2026-05-17
**작성자**: Claude (Phase 2-C.7 push 직후, 본 세션 종료 준비)
**다음 세션 첫 단계**: 사용자가 §7 의 Phase 3 후보 중 선택 → 첫 STEP 1 진단 보고서 작성
