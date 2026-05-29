# src/engine.py
from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, List
sys.path.insert(0, str(Path(__file__).parent))

from queries.tier1_hard import find_hard_clashes
from queries.tier2_conditional import find_conditional_clashes
from queries.tier3_layering import find_layering_rules, find_synergies

def analyze(ingredient_positions: Dict[str, int]) -> dict:
    """
    핵심 함수: 성분 목록 입력 → 충돌/시너지 종합 분석 결과 반환
    입력: {"레티놀": 3, "글라이콜릭애씨드": 2, ...}
    """
    ingredients = list(ingredient_positions.keys())

    hard    = find_hard_clashes(ingredients)
    cond    = find_conditional_clashes(ingredient_positions)
    layer   = find_layering_rules(ingredients)
    synergy = find_synergies(ingredients)

    score = len(hard) * 0.4 + len(cond) * 0.2 - len(synergy) * 0.1
    overall_score = round(min(max(score, 0.0), 1.0), 2)

    if hard:
        summary = f"🚨 절대 충돌 {len(hard)}건 — 함께 사용 금지"
    elif cond:
        summary = f"⚠️ 함량 주의 {len(cond)}건 — 소량 사용 권장"
    elif layer:
        summary = f"💡 순서 권장 {len(layer)}건 — 사용 순서를 지켜주세요"
    elif synergy:
        summary = f"✨ 시너지 {len(synergy)}건 — 함께 쓰면 효과 증가"
    else:
        summary = "✅ 충돌 없음 — 안전한 조합입니다"

    return {
        "hard_clashes":  hard,
        "conditional":   cond,
        "layering":      layer,
        "synergies":     synergy,
        "overall_score": overall_score,
        "summary":       summary
    }

def analyze_from_image(image_path: str) -> dict:
    """📸 사진 한 장으로 전체 분석"""
    from ocr_extractor import extract_ingredients_from_image
    print(f"📸 이미지 분석 중: {image_path}")
    ingredient_positions = extract_ingredients_from_image(image_path)
    print(f"✅ 추출된 성분 {len(ingredient_positions)}개")
    if not ingredient_positions:
        return {
            "hard_clashes": [],
            "conditional": [],
            "layering": [],
            "synergies": [],
            "overall_score": 0.0,
            "summary": "❌ 성분 추출 실패 — 이미지를 다시 확인해주세요"
        }
    return analyze(ingredient_positions)

if __name__ == "__main__":
    scenarios = [
        {
            "이름": "시나리오1: 레티놀 + AHA",
            "성분": {"레티놀": 3, "글라이콜릭애씨드": 2, "판테놀": 8}
        },
        {
            "이름": "시나리오2: 비타민C 황금 조합",
            "성분": {"아스코빅애씨드": 2, "토코페롤": 4, "페룰릭애씨드": 6}
        },
        {
            "이름": "시나리오3: 비타민C + 나이아신아마이드",
            "성분": {"아스코빅애씨드": 3, "나이아신아마이드": 2, "하이알루로닉애씨드": 5}
        },
        {
            "이름": "시나리오4: 레티놀 자극 완화",
            "성분": {"레티놀": 3, "하이알루로닉애씨드": 2, "세라마이드엔피": 4, "판테놀": 6}
        },
        {
            "이름": "시나리오5: 레티놀 + BPO",
            "성분": {"레티놀": 2, "벤조일퍼옥사이드": 3, "판테놀": 7}
        },
    ]

    for s in scenarios:
        print("\n" + "=" * 60)
        print(f"🧪 {s['이름']}")
        print("=" * 60)
        result = analyze(s['성분'])
        print(f"종합 위험도: {result['overall_score']}")
        print(f"요약: {result['summary']}")
        if result['hard_clashes']:
            print("❌ 절대 충돌:")
            for c in result['hard_clashes']:
                print(f"   {c['성분A']} + {c['성분B']}")
                print(f"   이유: {c['충돌이유'][:50]}")
        if result['synergies']:
            print("✨ 시너지:")
            for c in result['synergies']:
                print(f"   {c['성분A']} + {c['성분B']}")

def analyze_multi_products(products: List[Dict]) -> dict:
    """
    여러 제품 간 충돌 분석
    
    products: [
        {"name": "비타민C 세럼", "ingredients": {"아스코빅애씨드": 2, ...}},
        {"name": "레티놀 크림", "ingredients": {"레티놀": 3, ...}},
    ]
    """
    # 1. 모든 제품의 성분을 합치되, 어느 제품 출신인지 기록
    all_ingredients = {}      # {성분명: 평균순서}
    ingredient_to_products = {}  # {성분명: [제품명들]}
    
    for product in products:
        name = product["name"]
        for ing, pos in product["ingredients"].items():
            if ing not in all_ingredients:
                all_ingredients[ing] = pos
                ingredient_to_products[ing] = [name]
            else:
                # 같은 성분이 여러 제품에 있으면 순서 평균
                all_ingredients[ing] = (all_ingredients[ing] + pos) // 2
                ingredient_to_products[ing].append(name)
    
    # 2. 기존 analyze 함수로 충돌 분석
    result = analyze(all_ingredients)
    
    # 3. 각 충돌이 어느 제품 간 충돌인지 표시
    for clash in result["hard_clashes"]:
        a, b = clash["성분A"], clash["성분B"]
        products_a = ingredient_to_products.get(a, [])
        products_b = ingredient_to_products.get(b, [])
        # 다른 제품에 있는 경우만 진짜 충돌
        cross_product = [(pa, pb) for pa in products_a for pb in products_b if pa != pb]
        clash["충돌제품"] = cross_product
        clash["같은제품내"] = not cross_product  # 같은 제품 안에 있으면 무시
    
    # 같은 제품 안의 충돌은 필터링
    result["hard_clashes"] = [c for c in result["hard_clashes"] if not c.get("같은제품내")]
    
    return result