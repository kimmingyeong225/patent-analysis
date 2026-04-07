# 📌 임베딩 및 벡터 검색 파일
# 역할: 특허 텍스트를 벡터로 변환 + 유사도 검색
# 담당: 민경
# - OpenAI 임베딩 API 호출
# - FAISS 인덱스 생성 및 저장
# - 유사 특허 TOP 5 검색


import numpy as np
import faiss


# 청킹 로직

def chunk_patent(patent_info: dict) -> list[dict]:
    """
    특허 JSON(공개등록공보 필드)을 섹션별로 청크 리스트로 변환.

    반환 형식:
        [
            {
                "patent_id": "KR1020230012345",
                "section": "발명의 명칭",
                "text": "## 발명의 명칭\n태양광 패널 내장형 스마트워치 스트랩 ...",
            },
            ...
        ]
    """
    patent_id = patent_info.get("patent_id", "UNKNOWN")
    chunks = []

    # 1) 발명의 명칭
    title = patent_info.get("title", "").strip()
    if title:
        chunks.append({
            "patent_id": patent_id,
            "section": "발명의 명칭",
            "text": f"## 발명의 명칭\n{title}",
        })

    # 2) 요약 
    abstract = patent_info.get("abstract", "").strip()
    if abstract:
        chunks.append({
            "patent_id": patent_id,
            "section": "요약",
            "text": f"## 요약\n{abstract}",
        })

    # 3) 청구항 — 항목별로 개별 청크
    claims = patent_info.get("claims", [])
    for i, claim in enumerate(claims):
        claim = claim.strip()
        if not claim:
            continue
        # 청구범위 미제공 안내 문구는 청킹 의미 없으므로 건너뜀
        if "상세조회 API" in claim:
            continue
        chunks.append({
            "patent_id": patent_id,
            "section": f"청구항 {i + 1}",
            "text": f"## 청구항 {i + 1}\n{claim}",
        })

    return chunks


def chunk_patents(results: list[dict]) -> list[dict]:
    """
    /search 응답의 results 리스트 전체를 청킹.
    각 item의 '공개등록공보' 필드를 chunk_patent()에 넘긴다.
    """
    all_chunks = []
    for item in results:
        patent_info = item.get("공개등록공보", {})
        all_chunks.extend(chunk_patent(patent_info))
    return all_chunks


# 임베딩 

def get_embedding_dummy(text: str) -> np.ndarray:
    """테스트용 가짜 벡터 생성 (OpenAI 크레딧 없을 때 사용)"""
    np.random.seed(len(text))
    return np.random.rand(1536).astype("float32")


# 테스트

if __name__ == "__main__":
    from mock_data import MOCK_SEARCH_RESPONSE

    #  청킹 테스트 
    print("=" * 50)
    print("[ 청킹 테스트 ]")
    chunks = chunk_patents(MOCK_SEARCH_RESPONSE["results"])
    for chunk in chunks:
        print(f"\n[{chunk['patent_id']}] {chunk['section']}")
        print(chunk["text"])

    #  FAISS 테스트 
    print("\n" + "=" * 50)
    print("[ FAISS 테스트 ]")

    texts = [c["text"] for c in chunks]
    vectors = np.array([get_embedding_dummy(t) for t in texts])

    index = faiss.IndexFlatL2(1536)
    index.add(vectors)
    print(f"FAISS 인덱스 생성 완료! 저장된 청크 수: {index.ntotal}")

    query = "태양광 충전 웨어러블 기기"
    query_vector = np.array([get_embedding_dummy(query)])
    distances, indices = index.search(query_vector, 3)

    print(f"\n'{query}' 와 유사한 청크 TOP 3:")
    for rank, idx in enumerate(indices[0], 1):
        c = chunks[idx]
        print(f"{rank}위 [{c['patent_id']}] {c['section']} (거리: {distances[0][rank-1]:.4f})")
