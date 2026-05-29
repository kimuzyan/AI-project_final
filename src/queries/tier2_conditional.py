from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

def find_conditional_clashes(ingredient_positions: dict[str, int]) -> list[dict]:
    """
    함량 의존 충돌 탐지
    ingredient_positions: {성분명: 성분표 순서} - 숫자 작을수록 고함량
    """
    ingredients = list(ingredient_positions.keys())
    query = """
    UNWIND $ingredients AS name_a
    UNWIND $ingredients AS name_b
    WITH name_a, name_b WHERE name_a < name_b
    MATCH (a:Ingredient {kor_name: name_a})
    MATCH (b:Ingredient {kor_name: name_b})
    MATCH (a)-[r:CLASHES_WITH]->(b)
    WHERE r.tier = 'CONDITIONAL'
    RETURN
        a.kor_name   AS 성분A,
        b.kor_name   AS 성분B,
        r.severity   AS 심각도,
        r.confidence AS 신뢰도,
        r.mechanism  AS 충돌이유
    """
    with driver.session() as session:
        result = session.run(query, ingredients=ingredients)
        rows = [dict(row) for row in result]

    for row in rows:
        pos_a = ingredient_positions.get(row['성분A'], 99)
        pos_b = ingredient_positions.get(row['성분B'], 99)
        위험도 = row['신뢰도'] * (1 + max(0, (10 - pos_a - pos_b) / 10))
        row['위험도점수'] = round(min(위험도, 1.0), 3)
        row['판정'] = "⚠️ 주의" if 위험도 > 0.7 else "💛 낮은 위험"

    return sorted(rows, key=lambda x: x['위험도점수'], reverse=True)

if __name__ == "__main__":
    test = {"레티놀": 3, "글라이콜릭애씨드": 2, "판테놀": 10, "나이아신아마이드": 5}
    print("=== CONDITIONAL 충돌 탐지 테스트 ===")
    results = find_conditional_clashes(test)
    if not results:
        print("해당 없음 ✅")
    for r in results:
        print(f"{r['판정']} {r['성분A']} + {r['성분B']} (위험도: {r['위험도점수']})")
        print(f"   이유: {r['충돌이유']}")