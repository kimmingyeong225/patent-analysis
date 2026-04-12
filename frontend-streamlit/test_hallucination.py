# 📌 test_hallucination.py
# 역할: GPT 분석 결과에서 환각(hallucination)을 검출하는 테스트
# 담당: 팀원 3
#
# 사용법: python test_hallucination.py
# 필요: .env 파일에 OPENAI_API_KEY 설정

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from mock_data import MOCK_SEARCH_RESPONSE
from llm import analyze_novelty

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 테스트용 Mock 데이터 (backend/mock_data.py 에서 가져옴)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOCK_PATENTS = MOCK_SEARCH_RESPONSE["results"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 환각 검출 함수들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Mock 데이터에 존재하는 정보 집합 (화이트리스트)
KNOWN_PATENT_IDS = {p["공개등록공보"]["application_number"] for p in MOCK_PATENTS}
KNOWN_APPLICANTS = {p["공개등록공보"]["applicant"] for p in MOCK_PATENTS}
KNOWN_INVENTORS = set()
for p in MOCK_PATENTS:
    for name in p["공개등록공보"]["inventor"].split(", "):
        KNOWN_INVENTORS.add(name.strip())
KNOWN_TITLES = {p["공개등록공보"]["title"] for p in MOCK_PATENTS}
KNOWN_IPC_CODES = set()
for p in MOCK_PATENTS:
    for ipc in p["분류코드"]["ipc"]:
        KNOWN_IPC_CODES.add(ipc["code"])


def check_unknown_patent_ids(analysis: dict) -> list:
    """GPT가 제공되지 않은 특허 번호를 언급했는지 검사"""
    issues = []
    text = json.dumps(analysis, ensure_ascii=False)

    # 한국 특허 번호 패턴 검색
    import re
    found_ids = re.findall(r'10-\d{4}-\d{7}', text)
    for pid in found_ids:
        if pid not in KNOWN_PATENT_IDS:
            issues.append(f"🔴 알 수 없는 특허번호 언급: {pid}")

    # KR 패턴도 검색
    kr_ids = re.findall(r'KR\d{13}', text)
    known_kr = {p["공개등록공보"]["patent_id"] for p in MOCK_PATENTS}
    for kid in kr_ids:
        if kid not in known_kr:
            issues.append(f"🔴 알 수 없는 KR 특허번호 언급: {kid}")

    return issues


def check_unknown_companies(analysis: dict) -> list:
    """GPT가 제공되지 않은 회사/기관명을 언급했는지 검사"""
    issues = []
    text = json.dumps(analysis, ensure_ascii=False)

    # 흔히 환각으로 등장하는 회사명 패턴
    suspicious_companies = [
        "애플", "Apple", "구글", "Google", "화웨이", "Huawei",
        "소니", "Sony", "샤오미", "Xiaomi", "마이크로소프트",
        "현대", "SK", "포스텍", "서울대", "MIT", "Stanford"
    ]

    for company in suspicious_companies:
        if company in text:
            issues.append(f"🟡 제공되지 않은 기관/회사 언급: {company}")

    return issues


def check_fabricated_tech(analysis: dict) -> list:
    """GPT가 선행특허 데이터에 없는 기술을 지어냈는지 검사"""
    issues = []

    # 선행특허에 존재하는 핵심 기술 키워드
    known_tech = [
        "태양광", "유연성", "패널", "실리콘", "밀봉",
        "압전", "소자", "운동에너지", "공진",
        "체온", "열전", "발전", "방열", "온도"
    ]

    # five_aspects 내용에서 검사
    five = analysis.get("five_aspects", {})
    for aspect_key, aspect_text in five.items():
        # 아주 구체적인 수치가 포함되어 있으면 환각 의심
        import re
        specific_numbers = re.findall(r'\d{2,}%|\d+\.\d+', str(aspect_text))
        for num in specific_numbers:
            issues.append(f"🟡 [{aspect_key}] 출처 불명 수치 발견: {num} (데이터에 없는 수치)")

    return issues


def check_prior_art_accuracy(analysis: dict) -> list:
    """prior_art_comparison의 특허 정보가 실제 데이터와 일치하는지 검사"""
    issues = []
    comparisons = analysis.get("prior_art_comparison", [])

    for comp in comparisons:
        pid = comp.get("patent_id", "")
        title = comp.get("title", "")

        # 특허번호-제목 매칭 검사
        for p in MOCK_PATENTS:
            pub = p["공개등록공보"]
            if pid == pub["application_number"] and title != pub["title"]:
                issues.append(f"🔴 특허번호 {pid}의 제목이 불일치: '{title}' ≠ '{pub['title']}'")

        # 알 수 없는 특허번호
        if pid and pid not in KNOWN_PATENT_IDS:
            issues.append(f"🔴 prior_art_comparison에 알 수 없는 특허: {pid}")

    return issues


def check_score_consistency(analysis: dict) -> list:
    """신규성 점수와 리스크 수준의 논리적 일관성 검사"""
    issues = []
    score = analysis.get("novelty_score", 0)
    risk = analysis.get("risk_level", "")

    if isinstance(score, str):
        try:
            score = int(score)
        except ValueError:
            issues.append(f"🔴 novelty_score가 숫자가 아님: {score}")
            return issues

    # 점수가 높은데 리스크도 높으면 논리 모순
    if score >= 80 and risk == "높음":
        issues.append(f"🟡 논리 불일치: 신규성 {score}점인데 리스크 '높음'")

    # 점수가 낮은데 리스크도 낮으면 논리 모순
    if score <= 30 and risk == "낮음":
        issues.append(f"🟡 논리 불일치: 신규성 {score}점인데 리스크 '낮음'")

    return issues


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 테스트 케이스 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEST_CASES = [
    {
        "name": "기본 테스트 — Mock 데이터와 동일한 아이디어",
        "idea": "자가 충전형 스마트 워치 스트랩",
    },
    {
        "name": "모호한 입력 — GPT가 정보를 지어낼 유혹이 큰 경우",
        "idea": "AI를 활용한 차세대 에너지 하베스팅 웨어러블",
    },
    {
        "name": "관련 없는 입력 — 선행특허와 완전히 다른 분야",
        "idea": "블록체인 기반 식품 유통 이력 추적 시스템",
    },
    {
        "name": "매우 구체적 입력 — 존재하지 않는 기술 조합",
        "idea": "그래핀 나노튜브와 초전도체를 결합한 피부 부착형 마이크로 발전기",
    },
    {
        "name": "유사한 입력 — 선행특허와 거의 동일",
        "idea": "유연성 태양광 패널이 내장된 시계 밴드",
    },
]


def run_all_tests():
    print("=" * 70)
    print("🧪 환각(Hallucination) 테스트 시작")
    print("=" * 70)

    total_issues = 0

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n{'─' * 70}")
        print(f"📋 테스트 {i}/{len(TEST_CASES)}: {tc['name']}")
        print(f"   아이디어: {tc['idea']}")
        print(f"{'─' * 70}")

        analysis = analyze_novelty(tc["idea"], MOCK_PATENTS)

        if "error" in analysis:
            print(f"   ❌ 분석 실패: {analysis['error']}")
            total_issues += 1
            continue

        # 모든 검사 실행
        all_issues = []
        all_issues += check_unknown_patent_ids(analysis)
        all_issues += check_unknown_companies(analysis)
        all_issues += check_fabricated_tech(analysis)
        all_issues += check_prior_art_accuracy(analysis)
        all_issues += check_score_consistency(analysis)

        if all_issues:
            print(f"   ⚠️  환각 의심 항목 {len(all_issues)}건 발견:")
            for issue in all_issues:
                print(f"      {issue}")
            total_issues += len(all_issues)
        else:
            print("   ✅ 환각 없음 — 모든 검사 통과")

        # 주요 결과 요약 출력
        print(f"\n   신규성: {analysis.get('novelty_score', '?')}/100 | "
              f"리스크: {analysis.get('risk_level', '?')} | "
              f"선행특허비교: {len(analysis.get('prior_art_comparison', []))}건")

    # 최종 요약
    print(f"\n{'=' * 70}")
    print(f"📊 최종 결과: 전체 {len(TEST_CASES)}건 중 환각 의심 항목 총 {total_issues}건")
    if total_issues == 0:
        print("🎉 모든 테스트 통과!")
    else:
        print("⚠️  프롬프트 개선이 필요합니다.")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
