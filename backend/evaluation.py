# 성능 평가 파일
# - Precision@K, Recall@K 평가 지표 계산

from embedding import chunk_patents, build_faiss_index, search_similar
from mock_data import MOCK_SEARCH_RESPONSE

#  평가 지표 함수 

def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """
    Precision@K: 상위 K개 결과 중 관련 있는 비율
    retrieved: 검색된 patent_id 리스트
    relevant: 정답 patent_id 리스트
    """
    top_k = retrieved[:k]
    hits = len(set(top_k) & set(relevant))
    return hits / k


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """
    Recall@K: 전체 관련 문서 중 상위 K개에 포함된 비율
    """
    top_k = retrieved[:k]
    hits = len(set(top_k) & set(relevant))
    return hits / len(relevant) if relevant else 0.0


def average_precision(retrieved: list[str], relevant: list[str]) -> float:
    """
    Average Precision: 각 관련 문서가 등장할 때마다의 Precision 평균
    """
    hits = 0
    sum_precision = 0.0
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            hits += 1
            sum_precision += hits / (i + 1)
    return sum_precision / len(relevant) if relevant else 0.0


#  테스트 데이터셋 

# 쿼리별 관련 특허 정답 정의
TEST_CASES = [
    {
        "query": "태양광 에너지 충전 웨어러블 장치",
        "relevant_patents": ["KR1020230012345"],  # 태양광 스마트워치 스트랩
    },
    {
        "query": "자율주행 자동차 센서 융합 딥러닝",
        "relevant_patents": ["KR1020210056789"],  # 자율주행 센서 융합
    },
    {
        "query": "스마트폰 배터리 수명 연장 충전",
        "relevant_patents": ["KR1020220087654"],  # 배터리 충전 제어
    },
    {
        "query": "체온 발전 열전 에너지 변환",
        "relevant_patents": ["KR1020220087654"],  # 열전 발전 관련
    },
    {
        "query": "LiDAR 카메라 데이터 융합 객체 인식",
        "relevant_patents": ["KR1020210056789"],  # 센서 융합
    },
]


# 평가 실행 

if __name__ == "__main__":
    print("=" * 60)
    print("[ Phase 3: 성능 평가 - Precision@K / Recall@K ]")
    print("=" * 60)

    # 청킹 + FAISS 인덱스 생성
    chunks = chunk_patents(MOCK_SEARCH_RESPONSE["results"])
    index, chunks = build_faiss_index(chunks)

    k_values = [1, 3, 5]
    all_precisions = {k: [] for k in k_values}
    all_recalls = {k: [] for k in k_values}
    all_ap = []

    # 각 테스트 케이스 평가
    for i, test in enumerate(TEST_CASES):
        query = test["query"]
        relevant = test["relevant_patents"]

        results = search_similar(query, index, chunks, top_k=5)

        # 검색된 patent_id 리스트 (중복 제거, 순서 유지)
        retrieved_ids = []
        for r in results:
            if r["patent_id"] not in retrieved_ids:
                retrieved_ids.append(r["patent_id"])

        print(f"\n{'─' * 60}")
        print(f"테스트 {i+1}: \"{query}\"")
        print(f"  정답: {relevant}")
        print(f"  검색 결과: {retrieved_ids}")

        for k in k_values:
            p = precision_at_k(retrieved_ids, relevant, k)
            r = recall_at_k(retrieved_ids, relevant, k)
            all_precisions[k].append(p)
            all_recalls[k].append(r)
            print(f"  Precision@{k}: {p:.4f}  |  Recall@{k}: {r:.4f}")

        ap = average_precision(retrieved_ids, relevant)
        all_ap.append(ap)
        print(f"  AP: {ap:.4f}")
 
    print(f"\n{'=' * 60}")
    print("[ 전체 평균 성능 ]")
    print(f"{'=' * 60}")
    for k in k_values:
        mean_p = sum(all_precisions[k]) / len(all_precisions[k])
        mean_r = sum(all_recalls[k]) / len(all_recalls[k])
        print(f"  Mean Precision@{k}: {mean_p:.4f}")
        print(f"  Mean Recall@{k}:    {mean_r:.4f}")

    map_score = sum(all_ap) / len(all_ap)
    print(f"  MAP (Mean Average Precision): {map_score:.4f}")