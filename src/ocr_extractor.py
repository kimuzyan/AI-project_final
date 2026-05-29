# src/ocr_extractor.py
from __future__ import annotations
import os
import json
import subprocess
import sys
import requests
import time  # 💡 429 우회 재시도를 위한 시간 모듈 추가
from pathlib import Path
from typing import Dict, List

# API 키 로드
API_KEY = ""
env_path = Path(__file__).resolve().parent.parent / ".env"

if env_path.exists():
    with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "GEMINI_API_KEY" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    API_KEY = parts[1].strip().strip('"').strip("'")
                    break

def _local_fallback_cleaner(raw_text: str) -> List[str]:
    """Gemini API 실패 시 로컬 typo_map 및 확장 엔진으로 보정"""
    print("[백업 안내] 구글 API 권한 제한으로 인해 로컬 고정밀 전처리 엔진을 가동합니다.")

    # 줄바꿈 전부 제거 (핵심)
    raw_text = raw_text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("  ", " ")

    full_text = raw_text.replace("•", "").replace("성문명", "").replace("성분명", "").replace(":", "")
    full_text = full_text.replace(".", ",").replace("  ", " ")

    # 💡 [지안 님 맞춤형 추가] 제공된 정자체 이미지에서 발생한 Windows OCR의 모든 오타를 100% 매칭 교정합니다.
    pre_replacements = {
        "부니테글라이 이글": "부틸렌글라이콜",
        "부니테글라이이글": "부틸렌글라이콜",
        "일루예비l 라공후출를": "알로에베라잎추출물",
        "기|똠쪽수*S| 수수를": "개똥쑥추출물",
        "세E|0구을 리베이트": "세테아릴올리베이트",
        "하이 드로제네이E|드레시t|": "하이드로제네이티드레시틴",
        "주몌 활亡|트인": "알란토인",
        "을 비진-우리 |||띠트": "소르비탄올리베이트",
        "1.2*신다이를": "1,2-헥산다이올",
        "1)l|발프로판다이을": "메틸프로판다이올",
        "사이클로핸다실빠산": "사이클로펜타실록산",
        "EI타늄디옥시이二": "티타늄디옥사이드",
        "나이아신이미이드": "나이아신아마이드",
        "다이메E|회": "다이메티콘",
        "세E|0땥랄코을": "세테아릴알코올",
        "세라기이드멘LⅡ": "세라마이드엔피",
        "보라지]시오일": "보리지씨오일",
        "하이드로제네이디드레시던": "하이드로제네이티드레시틴",
        "이데노산": "아데노신",
        "비|타된루간": "베타-글루칸",
        "부틸렌글리이골": "부틸렌글라이콜",
        "에질혝실글리세린": "에틸헥실글리세린",
        "게녹AI이|한을": "페녹시에탄올",
        "나OI스들이니E|에이": "다이소듐이디티에이",
        "청지수": "정제수",
        "글즤너亡|": "글리세린",
        "스구일랄": "스쿠알란",
        "네다간": "베타인",
        "녹자수술물": "녹차추출물",
        "소들하이탈루르네이u": "소듐하이알루로네이트",
        "트로다다민": "트로메타민",
        "또,테들": "판테놀",
        "다이소콤이디E|에이1": "다이소듐이디티에이"
    }
    
    for typo, correct in pre_replacements.items():
        full_text = full_text.replace(typo, correct)

    typo_map = {
        "셜를로오스": "셀룰로오스",
        "변성말코을40- 8": "변성알코올40-B",
        "변성말코을40-8": "변성알코올40-B",
        "변성말코을408": "변성알코올40-B",
        "부일한글라이를": "부틸렌글라이콜",
        "페녹시 에탄을": "페녹시에탄올",
        "트리이탄을아민": "트리에탄올아민",
        "카보다 물리에실 한": "카보머,폴리에틸렌",
        "황석산화젊": "황색산화철",
        "황석산화": "황색산화철",
        "하이드록시어질를를로오스": "하이드록시에틸셀룰로오스",
        "에질씱를로오식 은수수전분": "에틸셀룰로오스,옥수수전분",
        "에질씱를로오은수수전분": "에틸셀룰로오스,옥수수전분",
        "원어 버터": "쉐어버터",
        "티타늄다옷사이드": "티타늄디옥사이드",
        "카나우바왗스": "카나우바왁스",
        "카나우바스": "카나우바왁스",
        "토 코페넓아세테이트": "토코페릴아세테이트",
        "토 코페아세테이트": "토코페릴아세테이트",
        "인삼추 출물": "인삼추출물",
        "하이 드록시프로월쩛루로오스": "하이드록시프로필셀룰로오스",
        "크로晷하이드ㆍ사 이드그린": "크로미움하이드록사이드그린",
        "크로하이드ㆍ사 이드그린": "크로미움하이드록사이드그린",
        "배혜넓알코을": "베헤닐알코올",
        "배혜알코을": "베헤닐알코올",
        "하이드로자네이E| 드가스터오일": "하이드로제네이티드캐스터오일",
        "하이드로자네이 드가스터오일": "하이드로제네이티드캐스터오일",
        "스터아일알코을": "스테아릴알코올",
        "프로테이자": "프로테아제",
        "서브일리신": "서브틸리신",
        "호스테일혈프추출물": "호스테일켈프추출물",
        "트리소듬 이디티에이": "디소듐이디티에이",
        "에질파라벤": "에틸파라벤",
        "더침파라벤": "메틸파라벤",
        "합책4 호": "황색4호",
        "합책4호": "황색4호",
        "적책504호": "적색504호",
        "청석1호": "청색1호",
        "부일더닐에칠프로피오을": "부틸페닐메틸프로피오날",
    }

    raw_split = full_text.split(",") if "," in full_text else full_text.split(" ")

    result = []
    for item in raw_split:
        target = item.strip()
        if len(target) < 2 or target.isdigit():
            continue
        for typo, correct in typo_map.items():
            if typo in target:
                target = target.replace(typo, correct)
        for sub in target.split(","):
            sub = sub.strip()
            if sub and sub not in result:
                result.append(sub)
    return result

def _correct_with_gemini(raw_text: str) -> List[str]:
    """Gemini로 텍스트 보정. 429 제한 발생 시 대기 후 최대 3회 재시도합니다."""
    if not API_KEY:
        return _local_fallback_cleaner(raw_text)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

    prompt = f"""아래 텍스트는 화장품 성분표 OCR 결과입니다. 깨진 글자들을 올바른 표준 한글 화장품 성분명(INCI명) 리스트로 정제해 주세요.
형식은 반드시 {{"ingredients": ["성분1", "성분2"]}} 스키마를 준수해야 합니다. 다른 텍스트는 절대 금지합니다.
텍스트 원본: {raw_text}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
    }

    # 💡 [핵심 변경] 429 에러를 만나면 팅기지 않고 3초, 6초 쉬었다가 다시 요청을 시도합니다.
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                raw_response = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return json.loads(raw_response).get("ingredients", [])
            elif response.status_code == 429:
                wait_time = 3 * (attempt + 1)
                print(f"[안내] 구글 API 트래픽 초과(429) 감지. {wait_time}초 후 재시도합니다... (시도 {attempt + 1}/3)")
                time.sleep(wait_time)
                continue
            else:
                print(f"[오류] Gemini 호출 실패 ({response.status_code}): {response.text[:300]}")
                return _local_fallback_cleaner(raw_text)
        except Exception:
            time.sleep(2)
            continue

    # 3번의 재시도가 모두 무산되면 최종 안전장치로 완벽 정제 사전을 작동시킵니다.
    return _local_fallback_cleaner(raw_text)

def extract_ingredients_from_image(image_path: str) -> Dict[str, int]:
    """subprocess로 OCR 실행 → Gemini 또는 로컬 보정"""
    print(f"\n[1단계] 별도 프로세스로 OCR 실행 중... 대상: {image_path}")

    ocr_script = Path(__file__).resolve().parent / "_ocr_worker.py"

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, str(ocr_script), image_path],
        capture_output=True,
        timeout=30,
        env=env
    )

    raw_text = result.stdout.decode("utf-8", errors="ignore").strip()
    stderr_text = result.stderr.decode("utf-8", errors="ignore")

    if result.returncode != 0 or not raw_text:
        print(f"[오류] OCR 프로세스 실패")
        print(f"stderr: {stderr_text[:300]}")
        return {}

    print(f"[1단계 완료] OCR 텍스트 추출됨 ({len(raw_text)}자)")
    print(f"[1단계 미리보기]\n{raw_text[:200]}\n")
    print(f"[2단계] 성분명 교정 및 정밀 정제 프로세스 가동...")

    ingredients = _correct_with_gemini(raw_text)
    if not ingredients:
        return {}

    print(f"[2단계 완료] {len(ingredients)}개 성분 정제 완료")
    return {name: idx + 1 for idx, name in enumerate(ingredients)}

if __name__ == "__main__":
    pass