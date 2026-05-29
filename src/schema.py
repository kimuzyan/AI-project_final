"""
schema.py
화장품 성분 충돌 분석 시스템 - 데이터 형식 정의

Python 3.8.6 + pydantic v1 (1.10.x) 호환
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, validator


# ============================================================
# Enum 정의
# ============================================================

class RelationType(str, Enum):
    """관계 타입 - 4가지 분류"""
    HARD        = "HARD"         # 절대 충돌 (함량 무관)
    CONDITIONAL = "CONDITIONAL"  # 함량 의존 충돌
    LAYERING    = "LAYERING"     # 사용 순서 권장
    SYNERGY     = "SYNERGY"      # 시너지 (긍정적 효과)


class Severity(str, Enum):
    """심각도 - 3단계"""
    HIGH   = "high"     # 매우 강한 충돌 또는 시너지
    MEDIUM = "medium"   # 중간 수준
    LOW    = "low"      # 약한 영향


class SourceType(str, Enum):
    """출처 타입"""
    PAPER  = "paper"   # 학술 논문
    BLOG   = "blog"    # 화학자 전문 블로그


class DataSource(str, Enum):
    """성분 데이터 출처"""
    KFDA    = "B (식약처)"
    C_V1    = "C (보강)"
    C_V2    = "C (2차 보강)"


# ============================================================
# Pydantic 모델
# ============================================================

class Ingredient(BaseModel):
    """
    성분 데이터 모델 (통합_성분_마스터_2074개.csv 한 행)
    
    CSV 컬럼:
        한글명, 영문명(INCI), CAS번호, 카테고리, 주요기능, 
        출처/설명, 이명, 데이터출처
    """
    kor_name:    str  = Field(..., description="한글명 (Neo4j primary key)")
    eng_name:    Optional[str] = Field(None, description="INCI 영문명")
    cas_no:      Optional[str] = Field(None, description="CAS 등록 번호")
    category:    Optional[str] = Field(None, description="성분 카테고리")
    function:    Optional[str] = Field(None, description="주요 기능")
    description: Optional[str] = Field(None, description="출처/설명")
    synonym:     Optional[str] = Field(None, description="이명/다른 표기")
    data_source: Optional[str] = Field(None, description="데이터 출처")
    
    @validator('kor_name')
    def kor_name_strip(cls, v):
        """한글명 앞뒤 공백 제거"""
        if not v or not v.strip():
            raise ValueError("한글명은 필수입니다")
        return v.strip()
    
    class Config:
        use_enum_values = True


class Relation(BaseModel):
    """
    관계쌍 데이터 모델 (관계쌍_전체_101개_학술근거.csv 한 행)
    
    CSV 컬럼:
        관계타입, 성분A, 성분B, 심각도, 신뢰도, 
        메커니즘유형, 상세메커니즘, 출처타입, 학술참조
    """
    relation_type:   RelationType = Field(..., description="HARD/CONDITIONAL/LAYERING/SYNERGY")
    ingredient_a:    str  = Field(..., description="성분 A 한글명")
    ingredient_b:    str  = Field(..., description="성분 B 한글명")
    severity:        Severity     = Field(..., description="심각도")
    confidence:      float        = Field(..., ge=0.0, le=1.0, description="신뢰도 0~1")
    mechanism_type:  str  = Field(..., description="메커니즘 유형")
    mechanism:       str  = Field(..., description="상세 메커니즘 설명")
    source_type:     SourceType   = Field(..., description="paper/blog")
    reference:       str  = Field(..., description="학술 참조 (논문 출처)")
    
    @validator('ingredient_a', 'ingredient_b')
    def name_strip(cls, v):
        """성분명 앞뒤 공백 제거"""
        if not v or not v.strip():
            raise ValueError("성분명은 필수입니다")
        return v.strip()
    
    @validator('ingredient_b')
    def check_different_ingredients(cls, v, values):
        """두 성분은 달라야 함"""
        if 'ingredient_a' in values and v == values['ingredient_a']:
            raise ValueError(f"성분 A와 B는 동일할 수 없습니다: {v}")
        return v
    
    class Config:
        use_enum_values = True


# ============================================================
# CSV 컬럼명 ↔ 모델 필드명 매핑
# ============================================================

INGREDIENT_CSV_MAPPING = {
    "한글명":      "kor_name",
    "영문명(INCI)": "eng_name",
    "CAS번호":     "cas_no",
    "카테고리":    "category",
    "주요기능":    "function",
    "출처/설명":   "description",
    "이명":        "synonym",
    "데이터출처":  "data_source",
}

RELATION_CSV_MAPPING = {
    "관계타입":     "relation_type",
    "성분A":        "ingredient_a",
    "성분B":        "ingredient_b",
    "심각도":       "severity",
    "신뢰도":       "confidence",
    "메커니즘유형": "mechanism_type",
    "상세메커니즘": "mechanism",
    "출처타입":     "source_type",
    "학술참조":     "reference",
}


# ============================================================
# 동작 확인용 메인
# ============================================================

if __name__ == "__main__":
    # Ingredient 테스트
    print("=" * 60)
    print("schema.py 동작 확인")
    print("=" * 60)
    
    sample_ing = Ingredient(
        kor_name="레티놀",
        eng_name="Retinol",
        cas_no="68-26-8",
        category="레티노이드",
        function="주름 개선·세포 재생",
        description="비타민A 알코올",
        synonym="비타민A",
        data_source="C (보강)"
    )
    print(f"\n[Ingredient 샘플]")
    print(f"  한글명: {sample_ing.kor_name}")
    print(f"  영문명: {sample_ing.eng_name}")
    print(f"  카테고리: {sample_ing.category}")
    
    # Relation 테스트
    sample_rel = Relation(
        relation_type="HARD",
        ingredient_a="레티놀",
        ingredient_b="벤조일퍼옥사이드",
        severity="high",
        confidence=0.97,
        mechanism_type="oxidation_destruction",
        mechanism="BPO 강산화 작용으로 레티놀 분자 파괴",
        source_type="paper",
        reference="Martin B et al., Br J Dermatol, 1998"
    )
    print(f"\n[Relation 샘플]")
    print(f"  타입: {sample_rel.relation_type}")
    print(f"  {sample_rel.ingredient_a} ↔ {sample_rel.ingredient_b}")
    print(f"  신뢰도: {sample_rel.confidence}")
    print(f"  심각도: {sample_rel.severity}")
    print(f"  메커니즘: {sample_rel.mechanism[:30]}...")
    
    print(f"\n✅ schema.py 정상 작동")