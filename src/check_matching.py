# -*- coding: utf-8 -*-
"""
check_matching.py
통합 성분 마스터 ↔ 관계쌍 데이터 정합성 검증
"""

import sys
from pathlib import Path
from typing import List, Set, Tuple

import pandas as pd
from pydantic import ValidationError

from schema import (
    Ingredient, 
    Relation, 
    INGREDIENT_CSV_MAPPING, 
    RELATION_CSV_MAPPING,
)

# 경로 설정
DATA_DIR = Path(__file__).parent.parent / "data"
MASTER_CSV = DATA_DIR / "통합_성분_마스터_2074개.csv"
RELATION_CSV = DATA_DIR / "관계쌍_전체_101개_학술근거.csv"
OUTPUT_REPORT = DATA_DIR / "검증_리포트.csv"

def load_master() -> pd.DataFrame:
    if not MASTER_CSV.exists():
        raise FileNotFoundError(f"마스터 파일이 없습니다: {MASTER_CSV}")
    df = pd.read_csv(MASTER_CSV, encoding='utf-8-sig')
    df = df.rename(columns=INGREDIENT_CSV_MAPPING)
    print(f"✅ 마스터 로드 완료: {len(df)}개 성분")
    return df

def load_relations() -> pd.DataFrame:
    if not RELATION_CSV.exists():
        raise FileNotFoundError(f"관계쌍 파일이 없습니다: {RELATION_CSV}")
    df = pd.read_csv(RELATION_CSV, encoding='utf-8-sig')
    df = df.rename(columns=RELATION_CSV_MAPPING)
    print(f"✅ 관계쌍 로드 완료: {len(df)}쌍")
    return df

def validate_ingredients(df: pd.DataFrame) -> Tuple[int, List[Tuple[int, str]]]:
    valid_count = 0
    errors = []
    for idx, row in df.iterrows():
        try:
            data = row.where(pd.notna(row), None).to_dict()
            Ingredient(**data)
            valid_count += 1
        except ValidationError as e:
            errors.append((idx, str(e)))
    return valid_count, errors

def validate_relations(df: pd.DataFrame) -> Tuple[int, List[Tuple[int, str]]]:
    valid_count = 0
    errors = []
    for idx, row in df.iterrows():
        try:
            data = row.where(pd.notna(row), None).to_dict()
            Relation(**data)
            valid_count += 1
        except ValidationError as e:
            errors.append((idx, str(e)))
    return valid_count, errors

def check_relation_matching(df_master: pd.DataFrame, df_rel: pd.DataFrame) -> Tuple[Set[str], List[dict]]:
    master_kor_set = set(df_master['kor_name'].dropna().str.strip())
    not_found: Set[str] = set()
    missing_rows: List[dict] = []
    
    for idx, row in df_rel.iterrows():
        a = str(row['ingredient_a']).strip()
        b = str(row['ingredient_b']).strip()
        a_missing = a not in master_kor_set
        b_missing = b not in master_kor_set
        
        if a_missing: not_found.add(a)
        if b_missing: not_found.add(b)
        if a_missing or b_missing:
            missing_rows.append({
                "row_index": idx, "relation_type": row['relation_type'],
                "ingredient_a": a, "ingredient_b": b,
                "a_missing": a_missing, "b_missing": b_missing,
            })
    return not_found, missing_rows

def print_statistics(df_master: pd.DataFrame, df_rel: pd.DataFrame):
    print("\n" + "=" * 60)
    print("📊 데이터 통계 리포트")
    print("=" * 60)
    print(f"\n[성분 마스터: {len(df_master)}개]")
    if 'data_source' in df_master.columns:
        for src, cnt in df_master['data_source'].value_counts().items():
            print(f"  - {src}: {cnt}개")
    print(f"\n[관계쌍: {len(df_rel)}쌍]")
    for rtype, cnt in df_rel['relation_type'].value_counts().items():
        print(f"  - {rtype}: {cnt}쌍")
    print(f"\n[심각도 분포]")
    for sev, cnt in df_rel['severity'].value_counts().items():
        print(f"  - {sev}: {cnt}쌍")
    print(f"\n[출처 분포]")
    for src, cnt in df_rel['source_type'].value_counts().items():
        print(f"  - {src}: {cnt}쌍")
    print(f"\n[가장 많이 등장하는 성분 TOP 5]")
    all_ings = pd.concat([df_rel['ingredient_a'], df_rel['ingredient_b']])
    top5 = all_ings.value_counts().head(5)
    for ing, cnt in top5.items():
        print(f"  - {ing}: {cnt}회")

def save_report(df_master: pd.DataFrame, df_rel: pd.DataFrame, missing_rows: List[dict], output_path: Path):
    report_data = [
        ["전체 성분 수",       len(df_master),                               "통합_성분_마스터"],
        ["전체 관계쌍",        len(df_rel),                                 "관계쌍_전체"],
        ["HARD 충돌",          len(df_rel[df_rel['relation_type']=='HARD']), "절대 충돌"],
        ["CONDITIONAL",        len(df_rel[df_rel['relation_type']=='CONDITIONAL']), "함량 의존"],
        ["LAYERING",           len(df_rel[df_rel['relation_type']=='LAYERING']), "순서 권장"],
        ["SYNERGY",            len(df_rel[df_rel['relation_type']=='SYNERGY']), "시너지"],
        ["학술 논문 출처",     len(df_rel[df_rel['source_type']=='paper']), "76%+"],
        ["블로그 출처",        len(df_rel[df_rel['source_type']=='blog']),  "24%"],
        ["매칭 실패 관계쌍",   len(missing_rows),                           "0이어야 정상"],
    ]
    df_report = pd.DataFrame(report_data, columns=['항목', '수치', '비고'])
    df_report.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n💾 검증 리포트 저장: {output_path}")

def main():
    print("=" * 60)
    print("🔍 데이터 정합성 검증 시작")
    print("=" * 60)
    df_master = load_master()
    df_rel = load_relations()
    
    print(f"\n[Pydantic 모델 검증]")
    valid_ings, ing_errors = validate_ingredients(df_master)
    print(f"  성분 검증: {valid_ings}/{len(df_master)} 통과")
    
    valid_rels, rel_errors = validate_relations(df_rel)
    print(f"  관계쌍 검증: {valid_rels}/{len(df_rel)} 통과")
    
    print(f"\n[마스터 ↔ 관계쌍 매칭 검증]")
    not_found, missing_rows = check_relation_matching(df_master, df_rel)
    
    if not not_found:
        print(f"  ✅ 모든 관계쌍 성분이 마스터에 존재 (100% 매칭)")
    else:
        print(f"  ❌ 매칭 실패 성분 {len(not_found)}개:")
        for ing in sorted(not_found): print(f"    - {ing}")
    
    print_statistics(df_master, df_rel)
    save_report(df_master, df_rel, missing_rows, OUTPUT_REPORT)
    
    print("\n" + "=" * 60)
    if not not_found and not ing_errors and not rel_errors:
        print("✅ 모든 검증 통과 - Neo4j 적재 준비 완료")
        print("=" * 60)
        return 0
    else:
        print("⚠️  일부 검증 실패 - 데이터 수정 필요")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())