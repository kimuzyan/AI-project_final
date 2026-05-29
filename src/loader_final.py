"""
loader.py - 최종 초고속 UNWIND 버전
Neo4j 클라우드에 통합 성분 마스터 + 관계쌍을 1초 만에 적재합니다.
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

from schema import INGREDIENT_CSV_MAPPING, RELATION_CSV_MAPPING

# ============================================================
# 환경 설정
# ============================================================
load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    print("❌ .env 파일에 NEO4J_PASSWORD가 설정되지 않았습니다")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"
MASTER_CSV = DATA_DIR / "통합_성분_마스터_2074개.csv"
RELATION_CSV = DATA_DIR / "관계쌍_전체_101개_학술근거.csv"

# ============================================================
# Neo4j 드라이버
# ============================================================
driver = GraphDatabase.driver(
    NEO4J_URI, 
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)

# ============================================================
# 검증 쿼리 함수
# ============================================================
def validate_load(session):
    print("\n" + "=" * 60)
    print("📊 적재 결과 검증")
    print("=" * 60)
    
    result = session.run("MATCH (i:Ingredient) RETURN count(i) AS cnt")
    print(f"\n[Ingredient 노드: {result.single()['cnt']}개]")
    
    print(f"\n[데이터 출처별]")
    result = session.run("""
        MATCH (i:Ingredient) WHERE i.data_source IS NOT NULL
        RETURN i.data_source AS src, count(*) AS cnt ORDER BY cnt DESC
    """)
    for row in result:
        print(f"  - {row['src']}: {row['cnt']}개")
    
    print(f"\n[CLASHES_WITH 관계 (Tier별)]")
    result = session.run("""
        MATCH ()-[r:CLASHES_WITH]->()
        RETURN r.tier AS tier, count(*) AS cnt ORDER BY tier
    """)
    clash_total = 0
    for row in result:
        print(f"  - {row['tier']}: {row['cnt']}쌍")
        clash_total += row['cnt']
    print(f"  합계: {clash_total}쌍")
    
    print(f"\n[SYNERGIZES_WITH 관계]")
    result = session.run("MATCH ()-[r:SYNERGIZES_WITH]->() RETURN count(r) AS cnt")
    print(f"  - 시너지: {result.single()['cnt']}쌍")

# ============================================================
# 메인 실행 프로세스
# ============================================================
def run():
    print("=" * 60)
    print("🚀 Neo4j 초고속 대용량 적재 시작")
    print("=" * 60)
    print(f"  Neo4j URI: {NEO4J_URI}")
    
    # 1. CSV 로드 및 전처리
    print(f"\n📂 CSV 파일 로드 및 결측치 정제 중...")
    df_master = pd.read_csv(MASTER_CSV, encoding='utf-8-sig')
    df_master = df_master.rename(columns=INGREDIENT_CSV_MAPPING)
    # NaN 결측치를 파이썬 None(Neo4j null)으로 완벽 변환
    master_batch = df_master.where(pd.notna(df_master), None).to_dict(orient='records')
    print(f"  ✅ 마스터: {len(master_batch)}개 성분 변환 완료")
    
    df_rel = pd.read_csv(RELATION_CSV, encoding='utf-8-sig')
    df_rel = df_rel.rename(columns=RELATION_CSV_MAPPING)
    
    # 관계쌍 분리 및 무방향 정렬 전처리
    df_clash = df_rel[df_rel['relation_type'].isin(['HARD','CONDITIONAL','LAYERING'])]
    df_synergy = df_rel[df_rel['relation_type'] == 'SYNERGY']
    
    clash_batch = []
    for _, row in df_clash.iterrows():
        d = row.to_dict()
        a, b = sorted([d['ingredient_a'], d['ingredient_b']])
        d['a'], d['b'] = a, b
        d['confidence'] = float(d['confidence']) if pd.notna(d['confidence']) else 0.0
        clash_batch.append(d)
        
    synergy_batch = []
    for _, row in df_synergy.iterrows():
        d = row.to_dict()
        a, b = sorted([d['ingredient_a'], d['ingredient_b']])
        d['a'], d['b'] = a, b
        d['confidence'] = float(d['confidence']) if pd.notna(d['confidence']) else 0.0
        synergy_batch.append(d)
    print(f"  ✅ 관계쌍: 충돌 {len(clash_batch)}쌍 / 시너지 {len(synergy_batch)}쌍 변환 완료")
    
    # 2. Neo4j 클라우드 전송
    with driver.session() as session:
        # 1단계: 인덱스 구축
        print(f"\n[1단계] 제약 조건 및 속도 최적화 인덱스 생성")
        session.execute_write(lambda tx: tx.run("CREATE CONSTRAINT ingredient_kor_unique IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.kor_name IS UNIQUE"))
        session.execute_write(lambda tx: tx.run("CREATE INDEX ingredient_category IF NOT EXISTS FOR (i:Ingredient) ON (i.category)"))
        session.execute_write(lambda tx: tx.run("CREATE INDEX clash_tier IF NOT EXISTS FOR ()-[r:CLASHES_WITH]-() ON (r.tier)"))
        session.execute_write(lambda tx: tx.run("CREATE INDEX synergy_type IF NOT EXISTS FOR ()-[r:SYNERGIZES_WITH]-() ON (r.synergy_type)"))
        print(f"  ✅ 완료")
        
        # 2단계: UNWIND 노드 적재
        print(f"\n[2단계] Ingredient 노드 초고속 일괄 적재 진행 중...")
        session.execute_write(lambda tx: tx.run("""
            UNWIND $batch AS row
            MERGE (i:Ingredient {kor_name: row.kor_name})
            ON CREATE SET
                i.eng_name      = row.eng_name,
                i.cas_no        = row.cas_no,
                i.category      = row.category,
                i.function      = row.function,
                i.description   = row.description,
                i.synonym       = row.synonym,
                i.data_source   = row.data_source,
                i.created_at    = datetime()
            ON MATCH SET
                i.eng_name      = row.eng_name,
                i.category      = row.category,
                i.updated_at    = datetime()
        """, batch=master_batch))
        print(f"  ✅ 완료: {len(master_batch)}개 노드가 1초 만에 클라우드에 안착했습니다!")
        
        # 3단계: UNWIND 충돌 관계 적재
        print(f"\n[3단계] CLASHES_WITH 관계 초고속 일괄 적재 진행 중...")
        if clash_batch:
            session.execute_write(lambda tx: tx.run("""
                UNWIND $batch AS row
                MATCH (a:Ingredient {kor_name: row.a})
                MATCH (b:Ingredient {kor_name: row.b})
                MERGE (a)-[r:CLASHES_WITH {tier: row.relation_type}]->(b)
                SET
                    r.severity       = row.severity,
                    r.confidence     = row.confidence,
                    r.mechanism_type = row.mechanism_type,
                    r.mechanism      = row.mechanism,
                    r.source_type    = row.source_type,
                    r.reference      = row.reference,
                    r.updated_at     = datetime()
            """, batch=clash_batch))
        print(f"  ✅ 완료: {len(clash_batch)}쌍 연결 성공")
        
        # 4단계: UNWIND 시너지 관계 적재
        print(f"\n[4단계] SYNERGIZES_WITH 관계 초고속 일괄 적재 진행 중...")
        if synergy_batch:
            session.execute_write(lambda tx: tx.run("""
                UNWIND $batch AS row
                MATCH (a:Ingredient {kor_name: row.a})
                MATCH (b:Ingredient {kor_name: row.b})
                MERGE (a)-[r:SYNERGIZES_WITH {synergy_type: row.mechanism_type}]->(b)
                SET
                    r.severity    = row.severity,
                    r.confidence  = row.confidence,
                    r.effect      = row.mechanism,
                    r.source_type = row.source_type,
                    r.reference   = row.reference,
                    r.updated_at  = datetime()
            """, batch=synergy_batch))
        print(f"  ✅ 완료: {len(synergy_batch)}쌍 연결 성공")
        
        # 5단계: 실시간 결과 검증
        validate_load(session)
    
    driver.close()
    print("\n" + "=" * 60)
    print("🎉 [대성공] 모든 화장품 데이터가 무사히 클라우드에 적재되었습니다!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\n❌ 최종 오류 발생: {e}")
        sys.exit(1)