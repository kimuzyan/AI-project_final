# src/ocr_server.py
# OCR 전용 독립 서버 (포트 8001)
# winsdk는 이 서버에서만 실행됨
from __future__ import annotations
import json
import asyncio
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
import tempfile
import os

import winsdk.windows.security.cryptography as crypto
import winsdk.windows.storage.streams as streams
import winsdk.windows.media.ocr as ocr
import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.globalization as globalization

# typo_map 보정 함수
def correct_ingredients(raw_text: str):
    raw_text = raw_text.replace("\n", " ").replace("  ", " ")
    typo_map = {
        "셜를로오스": "셀룰로오스", "변성말코을40- 8": "변성알코올40-B",
        "변성말코을40-8": "변성알코올40-B", "변성말코을408": "변성알코올40-B",
        "부일한글라이를": "부틸렌글라이콜", "페녹시 에탄을": "페녹시에탄올",
        "트리이탄을아민": "트리에탄올아민", "카보다 물리에실 한": "카보머,폴리에틸렌",
        "황석산화젊": "황색산화철", "황석산화": "황색산화철",
        "하이드록시어질를를로오스": "하이드록시에틸셀룰로오스",
        "에질씱를로오식 은수수전분": "에틸셀룰로오스,옥수수전분",
        "에질씱를로오은수수전분": "에틸셀룰로오스,옥수수전분",
        "원어 버터": "쉐어버터", "티타늄다옷사이드": "티타늄디옥사이드",
        "카나우바왗스": "카나우바왁스", "카나우바스": "카나우바왁스",
        "토 코페넓아세테이트": "토코페릴아세테이트", "토 코페아세테이트": "토코페릴아세테이트",
        "인삼추 출물": "인삼추출물", "스쿠일란": "스쿠알란",
        "하이 드록시프로월쩛루로오스": "하이드록시프로필셀룰로오스",
        "크로晷하이드ㆍ사 이드그린": "크로미움하이드록사이드그린",
        "크로하이드ㆍ사 이드그린": "크로미움하이드록사이드그린",
        "배혜넓알코을": "베헤닐알코올", "배혜알코을": "베헤닐알코올",
        "하이드로자네이E| 드가스터오일": "하이드로제네이티드캐스터오일",
        "하이드로자네이 드가스터오일": "하이드로제네이티드캐스터오일",
        "스터아일알코을": "스테아릴알코올", "프로테이자": "프로테아제",
        "서브일리신": "서브틸리신", "호스테일혈프추출물": "호스테일켈프추출물",
        "트리소듬 이디티에이": "디소듐이디티에이",
        "에질파라벤": "에틸파라벤", "더침파라벤": "메틸파라벤",
        "합책4 호": "황색4호", "합책4호": "황색4호",
        "적책504호": "적색504호", "청석1호": "청색1호",
        "부일더닐에칠프로피오을": "부틸페닐메틸프로피오날",
        "벤질원조에 이의 하이드晷시이소훡실3-사이를로역센카 복스일네치이드": "벤질벤조에이트,하이드록시이소헥실3-사이클로헥센카복스알데하이드",
    }
    full_text = raw_text.replace("•", "").replace("성분명", "").replace(":", "")
    full_text = full_text.replace(".", ",").replace("  ", " ")
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

import cv2
import numpy as np

def preprocess_image(image_path: str) -> str:
    """
    OCR 전 이미지 전처리:
    1. 3배 확대 (작은 글씨 대응)
    2. 흑백 변환
    3. 대비 강화
    4. 이진화 (글씨 선명하게)
    """
    img = cv2.imread(image_path)
    
    # 1. 3배 확대
    height, width = img.shape[:2]
    img = cv2.resize(img, (width * 3, height * 3), interpolation=cv2.INTER_CUBIC)
    
    # 2. 흑백 변환
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 3. 대비 강화 (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # 4. 이진화 (글씨 선명하게)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 5. 전처리된 이미지 임시 저장
    processed_path = image_path.replace(".", "_processed.")
    cv2.imwrite(processed_path, binary)
    
    return processed_path
async def _ocr_async(image_path: str):
    with open(image_path, "rb") as f:
        bytes_data = f.read()
    crypt_buffer = crypto.CryptographicBuffer.create_from_byte_array(bytes_data)
    stream = streams.InMemoryRandomAccessStream()
    await stream.write_async(crypt_buffer)
    stream.seek(0)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    target_lang = globalization.Language("ko-KR")
    engine = ocr.OcrEngine.try_create_from_language(target_lang)
    if not engine:
        engine = ocr.OcrEngine.try_create_from_language(
            ocr.OcrEngine.get_available_languages()[0]
        )
    result = await engine.recognize_async(software_bitmap)
    return [line.text for line in result.lines]

class OCRHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 로그 억제

    def do_POST(self):
        if self.path != "/ocr":
            self.send_response(404)
            self.end_headers()
            return

        # 파일 수신
        content_type = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(body)
            tmp_path = tmp.name

        try:
            # OCR 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            lines = loop.run_until_complete(_ocr_async(tmp_path))
            loop.close()

            raw_text = "\n".join(lines)
            ingredients = correct_ingredients(raw_text)
            result = {name: idx + 1 for idx, name in enumerate(ingredients)}

            # 응답
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8001), OCRHandler)
    print("✅ OCR 서버 실행 중: http://127.0.0.1:8001")
    server.serve_forever()