# src/main.py
from __future__ import annotations
import sys
import os
import tempfile
import asyncio
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from engine import analyze, analyze_multi_products

app = FastAPI(title="화장품 성분 분석 API - 루틴 추천 탑재 버전")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _calculate_recommended_routine(products: List[Dict]) -> List[Dict]:
    """성분을 분석하여 제품들의 최적 바르는 순서를 계산합니다."""
    scored_products = []
    
    for p in products:
        ings = list(p["ingredients"].keys())
        # 기본 점수 (2: 일반 수분/진정)
        score = 2 
        p_type = "수분 및 진정 단계"
        
        # 1. 강력한 액티브 성분 (AHA, BHA, 레티놀 등)이 있으면 가장 먼저 바름 (점수 1)
        if any(x in ings for x in ["락틱애씨드", "글라이콜릭애씨드", "살리실릭애씨드", "레티놀", "레티닐"]):
            score = 1
            p_type = "액티브 케어 및 각질 정돈 단계 (세안 직후 첫 단계 추천)"
        # 2. 무거운 오일이나 장벽 성분(세라마이드 등)이 있으면 맨 마지막에 바름 (점수 3)
        elif any(x in ings for x in ["세라마이드엔피", "세테아릴알코올", "시어버터", "보리지씨오일"]):
            score = 3
            p_type = "피부 장벽 보호 및 보습 봉인 단계 (마지막 마무리 추천)"
            
        scored_products.append((score, p["name"], p_type))
    
    # 점수 순으로 정렬 (1등 -> 2등 -> 3등)
    scored_products.sort(key=lambda x: x[0])
    
    routine = []
    for idx, (score, name, p_type) in enumerate(scored_products):
        routine.append({
            "순서": f"{idx + 1}단계",
            "제품명": name,
            "가이드": p_type
        })
    return routine

def _generate_custom_precautions(products: List[Dict]) -> List[str]:
    """검출된 성분 조합에 따른 맞춤형 피부 주의사항을 생성합니다."""
    all_ings = []
    for p in products:
        all_ings.extend(list(p["ingredients"].keys()))
        
    precautions = []
    
    # 1. 삼중 산성 + 레티놀 결합 경고
    has_acids = any(x in all_ings for x in ["락틱애씨드", "글라이콜릭애씨드", "살리실릭애씨드"])
    has_retinol = any(x in all_ings for x in ["레티놀", "레티닐"])
    
    if has_acids and has_retinol:
        precautions.append("⚠️ [고자극 삼중 결합 주의] AHA/BHA 계열의 각질 제거 성분과 레티놀이 동시에 사용됩니다. 피부 장벽에 자극을 줄 수 있으므로 반드시 밤(Night) 루틴에만 사용하시고, 초기에는 주 2~3회 격일 주기로 테스트하며 적응 기간을 가지세요.")
    
    # 2. 일반 레티놀 주의사항
    elif has_retinol:
        precautions.append("☀️ [자외선 차단 필수] 레티놀 성분은 빛과 열에 취약합니다. 낮에 사용 시 반드시 자외선 차단제를 함께 발라주셔야 피부를 보호할 수 있습니다.")
        
    # 3. 안전한 경우
    if not precautions:
        precautions.append("✅ 특이 자극을 유발하는 고위험 조합이 발견되지 않았습니다. 편안하게 루틴에 맞춰 사용하셔도 좋습니다.")
        
    return precautions


@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.post("/analyze/multi-images")
async def analyze_multi_images_endpoint(files: List[UploadFile] = File(...)):
    from ocr_extractor import extract_ingredients_from_image
    
    products = []
    loop = asyncio.get_event_loop()
    
    for idx, file in enumerate(files):
        if idx > 0:
            await asyncio.sleep(1.5)
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            ingredients = await loop.run_in_executor(None, extract_ingredients_from_image, tmp_path)
            products.append({
                "name": file.filename or f"제품{idx+1}",
                "ingredients": ingredients
            })
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    # 1. 기존 엔진 분석 결과 획득
    analysis_result = analyze_multi_products(products)
    
    # 2. 💡 [지안 님 요청 사항] 루틴 알고리즘 및 주의사항 데이터 주입
    analysis_result["recommended_routine"] = _calculate_recommended_routine(products)
    analysis_result["precautions"] = _generate_custom_precautions(products)
    
    return analysis_result

@app.post("/analyze")
def analyze_endpoint(ingredient_positions: Dict[str, int]):
    return analyze(ingredient_positions)

@app.get("/health")
def health():
    return {"status": "ok"}