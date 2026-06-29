import sys
import json
from pprint import pprint

from core.risk_detector import risk_detector_node
from core.evidence_retriever import evidence_retriever_node
from core.risk_judge import risk_judge_node

# 최소한의 룰셋 정의 (주차장 무료 vs 진짜 대출 무료, 100% 승인)
REVIEW_CRITERIA = {
    "risk_rules": [
        {
            "rule_id": "TEST_FREE",
            "risk_type": "fee_condition_missing",
            "base_level": "Medium",
            "keywords": ["무료"],
            "reason": "조건 없는 무료 제공 표현은 소비자를 오인하게 할 수 있습니다.",
            "evidence_query": "무료 서비스 고지",
        },
        {
            "rule_id": "TEST_APPROVAL",
            "risk_type": "approval_misleading",
            "base_level": "High",
            "keywords": ["100% 승인 보장", "누구나 승인"],
            "reason": "대출 승인 보장 표현은 부당권유 및 과장광고에 해당할 수 있습니다.",
            "evidence_query": "대출 승인 보장",
        },
    ],
    "required_disclaimers": []
}

def main():
    print("=== [1] 시작: 초기 State 구성 ===")
    # '무료 주차'는 오탐 케이스, '100% 승인 보장'은 진짜 위험 케이스
    state = {
        "extracted_text": "고객님 환영합니다. 방문 시 본 건물 지하에 무료 주차 가능합니다. 또한 이번 달 특별 대출 상품은 직장인이라면 누구나 100% 승인 보장 해드립니다!",
        "review_criteria": REVIEW_CRITERIA,
        "product_type": "신용대출",
        "enable_llm_risk_detection": True, # 하이브리드 탐지(AI 오탐 필터링) 켜기
        "risk_detection_model": "gpt-4o-mini",
        # Retrieval 세팅 (빠른 테스트를 위해 검색 AI 확장은 끔)
        "enable_llm_query_rewrite": False,
        "enable_llm_evidence_rerank": False,
    }
    
    print("\n=== [2] 노드 실행: risk_detector ===")
    state = risk_detector_node(state)
    detected = state.get("detected_risks", [])
    print(f"-> 최종 살아남은 위험 후보 수: {len(detected)}")
    for r in detected:
        print(f"   - 위험 키워드: {r.get('keyword')} (룰 등급: {r.get('base_level')})")
        
    print("\n(참고: 하이브리드 필터링 상세 정보)")
    pprint(state.get("risk_detection_detail"))

    print("\n=== [3] 노드 실행: evidence_retriever ===")
    state = evidence_retriever_node(state)
    evidences = state.get("evidence_list", [])
    print(f"-> Vector/BM25 병합 검색된 관련 법령 근거 수: {len(evidences)}")
    if evidences:
        print(f"   - 1위 검색 결과: {evidences[0].get('doc_title')} (스코어: {evidences[0].get('score')})")
        
    print("\n=== [4] 노드 실행: risk_judge (AI 개입 없는 100% 룰 기반) ===")
    state = risk_judge_node(state)
    
    print("\n=== [5] 최종 판단 결과 ===")
    print(f"최종 산정 등급: {state.get('risk_level')}")
    print(f"최종 코멘트 (Review-Assist Wording):\n{state.get('risk_reason')}")

if __name__ == "__main__":
    main()
