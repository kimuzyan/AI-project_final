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

def find_layering_rules(ingredient_list: list[str]) -> list[dict]:
    """순서만 지키면 되는 조합 탐지"""
    query = """
    UNWIND $ingredients AS name_a
    UNWIND $ingredients AS name_b
    WITH name_a, name_b WHERE name_a < name_b
    MATCH (a:Ingredient {kor_name: name_a})
    MATCH (b:Ingredient {kor_name: name_b})
    MATCH (a)-[r:CLASHES_WITH]->(b)
    WHERE r.tier = 'LAYERING'
    RETURN
        a.kor_name  AS 성분A,
        b.kor_name  AS 성분B,
        r.mechanism AS 권장순서,
        r.confidence AS 신뢰도
    """
    with driver.session() as session:
        result = session.run(query, ingredients=ingredient_list)
        return [dict(row) for row in result]

def find_synergies(ingredient_list: list[str]) -> list[dict]:
    """같이 쓰면 더 좋은 조합 탐지"""
    query = """
    UNWIND $ingredients AS name_a
    UNWIND $ingredients AS name_b
    WITH name_a, name_b WHERE name_a < name_b
    MATCH (a:Ingredient {kor_name: name_a})
    MATCH (b:Ingredient {kor_name: name_b})
    MATCH (a)-[r:SYNERGIZES_WITH]->(b)
    RETURN
        a.kor_name  AS 성분A,
        b.kor_name  AS 성분B,
        r.effect    AS 시너지효과,
        r.confidence AS 신뢰도
    ORDER BY r.confidence DESC
    """
    with driver.session() as session:
        result = session.run(query, ingredients=ingredient_list)
        return [dict(row) for row in result]

if __name__ == "__main__":
    test = ["아스코빅애씨드", "토코페롤", "페룰릭애씨드", "레티놀", "하이알루로닉애씨드"]
    print("=== LAYERING 규칙 ===")
    for r in find_layering_rules(test):
        print(f"💡 {r['성분A']} → {r['성분B']}: {r['권장순서']}")
    print("\n=== 시너지 조합 ===")
    for r in find_synergies(test):
        print(f"✨ {r['성분A']} + {r['성분B']}: {r['시너지효과']}")