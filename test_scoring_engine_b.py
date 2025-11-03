#!/usr/bin/env python3
"""
ScoreCalculator 경로 B (calculate_product_scores) 테스트 스크립트
"""

import asyncio
import sys
import os
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 필요한 모듈들 임포트
from app.services.scoring_engine import ScoreCalculator
from app.models.personalization_models import (
    ProfileMatchResult, ProductIngredientAnalysis, 
    IngredientEffect, SafetyLevel, EffectType
)

# 테스트용 Product 클래스 (실제 모델 대신)
@dataclass
class MockProduct:
    product_id: int
    name: str
    brand_name: str
    category_name: str
    tags: List[str]
    primary_attr: str = ""

# 테스트 데이터 생성
def create_test_products() -> List[MockProduct]:
    """테스트용 제품 데이터 생성"""
    return [
        MockProduct(
            product_id=1,
            name="수분 크림 (히알루론산)",
            brand_name="테스트브랜드A",
            category_name="스킨케어",
            tags=["보습", "수분", "히알루론산", "건성피부", "데일리"],
            primary_attr="보습력 강화"
        ),
        MockProduct(
            product_id=2,
            name="비타민C 세럼",
            brand_name="테스트브랜드B", 
            category_name="스킨케어",
            tags=["미백", "비타민C", "브라이트닝", "색소침착", "안티에이징"],
            primary_attr="미백 효과"
        ),
        MockProduct(
            product_id=3,
            name="레티놀 나이트 크림",
            brand_name="테스트브랜드C",
            category_name="스킨케어", 
            tags=["레티놀", "주름개선", "안티에이징", "탄력", "성숙피부"],
            primary_attr="주름 개선"
        ),
        MockProduct(
            product_id=4,
            name="센텔라 진정 토너",
            brand_name="테스트브랜드D",
            category_name="스킨케어",
            tags=["진정", "센텔라", "민감피부", "수딩", "저자극"],
            primary_attr="진정 효과"
        ),
        MockProduct(
            product_id=5,
            name="살리실산 BHA 필링",
            brand_name="테스트브랜드E",
            category_name="스킨케어",
            tags=["BHA", "살리실산", "각질제거", "모공케어", "지성피부"],
            primary_attr="각질 제거"
        )
    ]

def create_test_profile_matches() -> Dict[int, ProfileMatchResult]:
    """테스트용 프로필 매칭 결과 생성"""
    return {
        1: ProfileMatchResult(
            user_id=None,
            product_id=1,
            overall_match_score=85.0,
            age_match_score=90.0,
            skin_type_match_score=95.0,
            preference_match_score=80.0,
            match_reasons=["건성피부에 적합", "20대 연령층에 맞음", "보습 고민 해결"]
        ),
        2: ProfileMatchResult(
            user_id=None,
            product_id=2,
            overall_match_score=75.0,
            age_match_score=80.0,
            skin_type_match_score=70.0,
            preference_match_score=85.0,
            match_reasons=["미백 효과 우수", "색소침착 개선"]
        ),
        3: ProfileMatchResult(
            user_id=None,
            product_id=3,
            overall_match_score=60.0,
            age_match_score=40.0,  # 20대에게는 낮은 점수
            skin_type_match_score=75.0,
            preference_match_score=80.0,
            match_reasons=["주름 개선 효과", "연령대 부적합"]
        ),
        4: ProfileMatchResult(
            user_id=None,
            product_id=4,
            overall_match_score=90.0,
            age_match_score=95.0,
            skin_type_match_score=100.0,  # 민감피부에 완벽
            preference_match_score=85.0,
            match_reasons=["민감피부에 최적", "진정 효과 탁월", "저자극 성분"]
        ),
        5: ProfileMatchResult(
            user_id=None,
            product_id=5,
            overall_match_score=70.0,
            age_match_score=85.0,
            skin_type_match_score=60.0,  # 건성피부에는 부적합
            preference_match_score=75.0,
            match_reasons=["각질 제거 효과", "건성피부에 부적합"]
        )
    }

def create_test_ingredient_analyses() -> Dict[int, ProductIngredientAnalysis]:
    """테스트용 성분 분석 결과 생성"""
    return {
        1: ProductIngredientAnalysis(
            product_id=1,
            product_name="수분 크림 (히알루론산)",
            total_ingredients=15,
            analyzed_ingredients=12,
            harmful_effects=[],  # 안전한 제품
            beneficial_effects=[
                IngredientEffect(
                    ingredient_id=1,
                    ingredient_name="히알루론산",
                    effect_type=EffectType.BENEFICIAL,
                    effect_description="강력한 보습 효과",
                    confidence_score=0.9,
                    safety_level=SafetyLevel.SAFE
                )
            ],
            safety_warnings=[],
            allergy_risks=["향료 알레르기 주의"]
        ),
        2: ProductIngredientAnalysis(
            product_id=2,
            product_name="비타민C 세럼",
            total_ingredients=18,
            analyzed_ingredients=15,
            harmful_effects=[],
            beneficial_effects=[
                IngredientEffect(
                    ingredient_id=2,
                    ingredient_name="비타민C",
                    effect_type=EffectType.BENEFICIAL,
                    effect_description="미백 및 항산화 효과",
                    confidence_score=0.95,
                    safety_level=SafetyLevel.SAFE
                )
            ],
            safety_warnings=["햇빛 노출 시 주의"],
            allergy_risks=[]
        ),
        3: ProductIngredientAnalysis(
            product_id=3,
            product_name="레티놀 나이트 크림",
            total_ingredients=20,
            analyzed_ingredients=16,
            harmful_effects=[
                IngredientEffect(
                    ingredient_id=3,
                    ingredient_name="레티놀",
                    effect_type=EffectType.HARMFUL,
                    effect_description="초기 자극 가능성",
                    confidence_score=0.7,
                    safety_level=SafetyLevel.CAUTION
                )
            ],
            beneficial_effects=[
                IngredientEffect(
                    ingredient_id=31,
                    ingredient_name="레티놀",
                    effect_type=EffectType.BENEFICIAL,
                    effect_description="주름 개선 효과",
                    confidence_score=0.95,
                    safety_level=SafetyLevel.CAUTION
                )
            ],
            safety_warnings=["임신/수유 중 사용 금지", "점진적 사용 권장"],
            allergy_risks=[]
        ),
        4: ProductIngredientAnalysis(
            product_id=4,
            product_name="센텔라 진정 토너",
            total_ingredients=12,
            analyzed_ingredients=12,
            harmful_effects=[],
            beneficial_effects=[
                IngredientEffect(
                    ingredient_id=4,
                    ingredient_name="센텔라아시아티카",
                    effect_type=EffectType.BENEFICIAL,
                    effect_description="진정 및 항염 효과",
                    confidence_score=0.9,
                    safety_level=SafetyLevel.SAFE
                )
            ],
            safety_warnings=[],
            allergy_risks=[]
        ),
        5: ProductIngredientAnalysis(
            product_id=5,
            product_name="살리실산 BHA 필링",
            total_ingredients=16,
            analyzed_ingredients=14,
            harmful_effects=[
                IngredientEffect(
                    ingredient_id=5,
                    ingredient_name="살리실산",
                    effect_type=EffectType.HARMFUL,
                    effect_description="과도한 건조 가능성",
                    confidence_score=0.8,
                    safety_level=SafetyLevel.CAUTION
                )
            ],
            beneficial_effects=[
                IngredientEffect(
                    ingredient_id=51,
                    ingredient_name="살리실산",
                    effect_type=EffectType.BENEFICIAL,
                    effect_description="각질 제거 및 모공 개선",
                    confidence_score=0.9,
                    safety_level=SafetyLevel.CAUTION
                )
            ],
            safety_warnings=["건성피부 사용 주의", "과도한 사용 금지"],
            allergy_risks=["살리실산 알레르기"]
        )
    }

async def test_calculate_product_scores():
    """경로 B 테스트 실행"""
    print("🧪 ScoreCalculator 경로 B 테스트 시작")
    print("=" * 60)
    
    # 1. 테스트 데이터 준비
    products = create_test_products()
    intent_tags = ["보습", "미백", "진정"]  # 사용자 의도
    profile_matches = create_test_profile_matches()
    ingredient_analyses = create_test_ingredient_analyses()
    
    # 사용자 프로필 (20대 건성 민감피부)
    user_profile = {
        "age_group": "20s",
        "skin_type": "dry",
        "skin_concerns": ["dryness", "sensitivity"],
        "allergies": []
    }
    
    # 커스텀 가중치 (안전성을 더 중요하게)
    custom_weights = {
        "intent": 25.0,
        "personalization": 35.0, 
        "safety": 40.0
    }
    
    print(f"📋 테스트 설정:")
    print(f"   제품 수: {len(products)}")
    print(f"   의도 태그: {intent_tags}")
    print(f"   사용자 프로필: {user_profile}")
    print(f"   가중치: {custom_weights}")
    print()
    
    # 2. ScoreCalculator 초기화 및 실행
    try:
        calculator = ScoreCalculator()
        
        print("⏳ 점수 계산 중...")
        start_time = asyncio.get_event_loop().time()
        
        # 경로 B 실행
        results = await calculator.calculate_product_scores(
            products=products,
            intent_tags=intent_tags,
            profile_matches=profile_matches,
            ingredient_analyses=ingredient_analyses,
            user_profile=user_profile,
            custom_weights=custom_weights
        )
        
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time
        
        print(f"✅ 계산 완료 (소요시간: {execution_time:.3f}초)")
        print()
        
        # 3. 결과 분석 및 출력
        print("📊 점수 계산 결과:")
        print("-" * 60)
        
        # 점수순으로 정렬
        sorted_results = sorted(
            results.items(), 
            key=lambda x: x[1].final_score, 
            reverse=True
        )
        
        for rank, (product_id, score) in enumerate(sorted_results, 1):
            product = next(p for p in products if p.product_id == product_id)
            
            print(f"{rank}. 제품 ID {product_id}: {product.name}")
            print(f"   브랜드: {product.brand_name}")
            print(f"   최종점수: {score.final_score:.1f} (정규화: {score.normalized_score:.1f})")
            print(f"   세부점수:")
            print(f"     - 의도 매칭: {score.score_breakdown.intent_score:.1f}")
            print(f"     - 개인화: {score.score_breakdown.personalization_score:.1f}")
            print(f"     - 안전성: {score.score_breakdown.safety_score:.1f}")
            print(f"   추천 이유: {', '.join(score.recommendation_reasons[:3])}")
            if score.caution_notes:
                print(f"   주의사항: {', '.join(score.caution_notes[:2])}")
            print()
        
        # 4. 통계 정보
        scores_list = [s.final_score for s in results.values()]
        print("📈 통계 정보:")
        print(f"   평균 점수: {sum(scores_list) / len(scores_list):.1f}")
        print(f"   최고 점수: {max(scores_list):.1f}")
        print(f"   최저 점수: {min(scores_list):.1f}")
        print(f"   점수 범위: {max(scores_list) - min(scores_list):.1f}")
        
        return results
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_different_scenarios():
    """다양한 시나리오 테스트"""
    print("\n" + "=" * 60)
    print("🔄 다양한 시나리오 테스트")
    print("=" * 60)
    
    products = create_test_products()
    profile_matches = create_test_profile_matches()
    ingredient_analyses = create_test_ingredient_analyses()
    calculator = ScoreCalculator()
    
    scenarios = [
        {
            "name": "시나리오 1: 보습 중심 (건성피부)",
            "intent_tags": ["보습", "수분"],
            "user_profile": {"age_group": "20s", "skin_type": "dry"},
            "weights": {"intent": 50.0, "personalization": 30.0, "safety": 20.0}
        },
        {
            "name": "시나리오 2: 안티에이징 중심 (30대)",
            "intent_tags": ["안티에이징", "주름개선"],
            "user_profile": {"age_group": "30s", "skin_type": "normal"},
            "weights": {"intent": 40.0, "personalization": 40.0, "safety": 20.0}
        },
        {
            "name": "시나리오 3: 안전성 우선 (민감피부)",
            "intent_tags": ["진정", "민감케어"],
            "user_profile": {"age_group": "20s", "skin_type": "sensitive"},
            "weights": {"intent": 20.0, "personalization": 30.0, "safety": 50.0}
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 {scenario['name']}")
        print(f"   의도: {scenario['intent_tags']}")
        print(f"   프로필: {scenario['user_profile']}")
        print(f"   가중치: {scenario['weights']}")
        
        try:
            results = await calculator.calculate_product_scores(
                products=products,
                intent_tags=scenario['intent_tags'],
                profile_matches=profile_matches,
                ingredient_analyses=ingredient_analyses,
                user_profile=scenario['user_profile'],
                custom_weights=scenario['weights']
            )
            
            # 상위 3개 제품만 출력
            sorted_results = sorted(
                results.items(), 
                key=lambda x: x[1].final_score, 
                reverse=True
            )[:3]
            
            print("   상위 3개 제품:")
            for rank, (product_id, score) in enumerate(sorted_results, 1):
                product = next(p for p in products if p.product_id == product_id)
                print(f"     {rank}. {product.name} (점수: {score.final_score:.1f})")
                
        except Exception as e:
            print(f"   ❌ 시나리오 실패: {e}")

if __name__ == "__main__":
    async def main():
        # 기본 테스트
        results = await test_calculate_product_scores()
        
        if results:
            # 추가 시나리오 테스트
            await test_different_scenarios()
            
            print("\n✅ 모든 테스트 완료!")
        else:
            print("\n❌ 테스트 실패로 인해 추가 테스트를 건너뜁니다.")
    
    # 이벤트 루프 실행
    asyncio.run(main())