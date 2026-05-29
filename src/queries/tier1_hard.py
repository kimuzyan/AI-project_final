# src/queries/tier1_hard.py
from __future__ import annotations 
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
print(f"[디버그] .env 경로: {env_path}")
print(f"[디버그] 파일 존재 여부: {env_path.exists()}")
load_dotenv(env_path)

# ✅ 실제 읽힌 값 확인 (비밀번호 앞 5자리만 출력)
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
print(f"[디버그] URI: {NEO4J_URI}")
print(f"[디버그] USER: {NEO4J_USER}")
print(f"[디버그] PASSWORD 앞5자리: {NEO4J_PASSWORD[:5] if NEO4J_PASSWORD else 'None'}")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

def find_hard_clashes(ingredient_list: list[str]) -> list[dict]:
    query = """
    UNWIND $ingredients AS name_a
    UNWIND $ingredients AS name_b
    WITH name_a, name_b WHERE name_a < name_b
    MATCH (a:Ingredient {kor_name: name_a})
    MATCH (b:Ingredient {kor_name: name_b})
    MATCH (a)-[r:CLASHES_WITH]->(b)
    WHERE r.tier = 'HARD'
    RETURN 
        a.kor_name   AS 성분A,
        b.kor_name   AS 성분B,
        r.severity   AS 심각도,
        r.confidence AS 신뢰도,
        r.mechanism  AS 충돌이유
    ORDER BY r.confidence DESC
    """
    with driver.session() as session:
        result = session.run(query, ingredients=ingredient_list)
        return [dict(row) for row in result]

if __name__ == "__main__":
    test_ingredients = ["레티놀", "글라이콜릭애씨드", "나이아신아마이드", "아스코빅애씨드"]
    
    print("=== HARD 충돌 탐지 테스트 ===")
    clashes = find_hard_clashes(test_ingredients)
    
    if not clashes:
        print("충돌 없음 ✅")
    for c in clashes:
        print(f"❌ {c['성분A']} + {c['성분B']}")
        print(f"   심각도: {c['심각도']} | 신뢰도: {c['신뢰도']}")
        print(f"   이유: {c['충돌이유']}")