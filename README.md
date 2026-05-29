## 설치 방법

# 1. 패키지 설치
pip install -r requirements.txt

# 2. .env 파일 생성 (.env.example 복사)
# .env.example을 .env로 이름 바꾸고 실제 값 입력

# 3. OCR 서버 실행 (PowerShell 창 1)
python src/ocr_server.py

# 4. FastAPI 서버 실행 (PowerShell 창 2)
python -m uvicorn src.main:app --reload
