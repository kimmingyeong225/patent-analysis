# 📌 임베딩 및 벡터 검색 파일
# 역할: 특허 텍스트를 벡터로 변환 + 코사인 유사도 기반 FAISS 검색
# 담당: 민경

import numpy as np
import faiss
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ──────────────── 임베딩 ────────────────

def get_embedding(text: str) -> np.ndarray:
    """OpenAI text-embedding-3-small로 진짜 벡터 생성"""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return np.array(response.data[0].embedding, dtype="float32")


# ──────────────── 청킹 ────────────────

def chunk_patent(patent_info: dict) -> list[dict]:
    """
    특허 JSON(공개등록공보 필드)을 섹션별로 청크 리스트로 변환.
    문서 레벨 메타데이터(제목)를 각 청크 앞에 주입하여 검색 정확도 향상.
    """
    patent_id = patent_info.get("patent_id", "UNKNOWN")
    title = patent_info.get("title", "").strip()
    abstract = patent_info.get("abstract", "").strip()
    claims = patent_info.get("claims", [])
    
    # 메타데이터 컨텍스트 (각 청크 앞에 붙임)
    context_prefix = f"[특허: {title}] " if title else ""
    
    chunks = []

    # 1) 제목 + 요약 통합 청크 (가장 중요)
    if title or abstract:
        combined = f"{title}. {abstract}" if abstract else title
        chunks.append({
            "patent_id": patent_id,
            "section": "제목+요약",
            "text": f"{context_prefix}{combined}",
        })

    # 2) 청구항 — 항목별로 개별 청크
    for i, claim in enumerate(claims):
        claim = claim.strip() if isinstance(claim, str) else ""
        if not claim:
            continue
        if "상세조회 API" in claim:
            continue
        chunks.append({
            "patent_id": patent_id,
            "section": f"청구항 {i + 1}",
            "text": f"{context_prefix}청구항 {i + 1}: {claim}",
        })

    return chunks


def chunk_patents(results: list[dict]) -> list[dict]:
    """검색 결과 리스트 전체를 청킹"""
    all_chunks = []
    for item in results:
        patent_info = item.get("공개등록공보", {})
        all_chunks.extend(chunk_patent(patent_info))
    return all_chunks


# FAISS (코사인 유사도) 

def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """L2 정규화 — 내적(IP)이 코사인 유사도와 동일해짐"""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1  # 0벡터 방지
    return vectors / norms


def build_faiss_index(chunks: list[dict]):
    """
    청크 리스트 → 임베딩 → 코사인 유사도 FAISS 인덱스 생성
    반환: (index, chunks, vectors)
    """
    texts = [c["text"] for c in chunks]
    
    # 진짜 OpenAI 임베딩
    vectors = np.array([get_embedding(t) for t in texts])
    
    # L2 정규화 (코사인 유사도용)
    vectors = normalize_vectors(vectors)
    
    # IndexFlatIP = 내적 기반 → 정규화된 벡터에서는 코사인 유사도
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    
    print(f"✅ FAISS 인덱스 생성 완료! 저장된 청크 수: {index.ntotal}")
    return index, chunks


def search_similar(query: str, index, chunks: list[dict], top_k: int = 5):
    """쿼리 → 임베딩 → 코사인 유사도 TOP K 검색"""
    query_vector = np.array([get_embedding(query)])
    query_vector = normalize_vectors(query_vector)
    
    scores, indices = index.search(query_vector, min(top_k, index.ntotal))
    
    results = []
    for rank, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        chunk = chunks[idx]
        results.append({
            "rank": rank + 1,
            "patent_id": chunk["patent_id"],
            "section": chunk["section"],
            "text": chunk["text"],
            "similarity_score": round(float(scores[0][rank]), 4)
        })
    return results


# 테스트

if __name__ == "__main__":
    from mock_data import MOCK_SEARCH_RESPONSE

    print("=" * 50)
    print("[ 청킹 테스트 ]")
    chunks = chunk_patents(MOCK_SEARCH_RESPONSE["results"])
    for c in chunks:
        print(f"  [{c['patent_id']}] {c['section']}")

    print("\n" + "=" * 50)
    print("[ OpenAI 임베딩 + 코사인 유사도 FAISS 테스트 ]")
    index, chunks = build_faiss_index(chunks)

    query = "태양광 충전 웨어러블 기기"
    results = search_similar(query, index, chunks, top_k=3)

    print(f"\n🔍 '{query}' 유사 특허 TOP 3:")
    for r in results:
        print(f"  {r['rank']}위: [{r['patent_id']}] {r['section']} "
              f"(유사도: {r['similarity_score']})")