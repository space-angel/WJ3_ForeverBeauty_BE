#!/usr/bin/env python3
"""
추천 엔진 전체 플로우 테스트
배포 전 로컬에서 모든 기능을 검증합니다.
"""
import asyncio
import sys
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

async def test_basic_recommendation():
    """기본 추천 테스트 (의약품 없음)"""
    print("🧪 기본 추천 테스트...")
    
    try:
        from app.models.request import RecommendationRequest, UserProfile
        from app.services.recommendation_engine import RecommendationEngine
        
        # 요청 생성
        request = RecommendationRequest(
            intent_tags=["moisturizing", "anti-aging"],
            user_profile=UserProfile(
                age_group="30s",
                skin_type="dry"
            ),
            top_n=3
        )
        
        # 추천 엔진 실행
        engine = RecommendationEngine()
        response = await engine.recommend(request)
        
        print(f"✅ 기본 추천 성공:")
        print(f"  - 요청 ID: {response.execution_summary.request_id}")
        print(f"  - 실행 시간: {response.execution_summary.execution_time_seconds:.3f}초")
        print(f"  - 추천 개수: {len(response.recommendations)}개")
        print(f"  - 전체 후보: {response.pipeline_statistics.total_candidates}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 기본 추천 실패: {e}")
        return False

async def test_medication_recommendation():
    """의약품 포함 추천 테스트"""
    print("\n💊 의약품 포함 추천 테스트...")
    
    try:
        from app.models.request import RecommendationRequest, UserProfile, MedicationInfo
        from app.services.recommendation_engine import RecommendationEngine
        
        # 요청 생성 (와파린 복용자)
        request = RecommendationRequest(
            intent_tags=["moisturizing", "anti-aging"],
            user_profile=UserProfile(
                age_group="30s",
                skin_type="dry"
            ),
            medications=[
                MedicationInfo(
                    name="와파린",
                    active_ingredients=["B01AA03"]
                )
            ],
            top_n=3
        )
        
        # 추천 엔진 실행
        engine = RecommendationEngine()
        response = await engine.recommend(request)
        
        print(f"✅ 의약품 추천 성공:")
        print(f"  - 요청 ID: {response.execution_summary.request_id}")
        print(f"  - 실행 시간: {response.execution_summary.execution_time_seconds:.3f}초")
        print(f"  - 추천 개수: {len(response.recommendations)}개")
        print(f"  - 배제된 제품: {response.pipeline_statistics.excluded_by_rules}개")
        print(f"  - 감점된 제품: {response.pipeline_statistics.penalized_products}개")
        print(f"  - 적용된 배제 룰: {response.pipeline_statistics.eligibility_rules_applied}개")
        print(f"  - 적용된 감점 룰: {response.pipeline_statistics.scoring_rules_applied}개")
        
        # 룰 적용 여부 확인
        if response.pipeline_statistics.eligibility_rules_applied > 0 or response.pipeline_statistics.scoring_rules_applied > 0:
            print("🎯 룰 적용 확인됨!")
        else:
            print("⚠️  룰이 적용되지 않았습니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 의약품 추천 실패: {e}")
        return False

async def test_anticoagulant_recommendation():
    """항응고제 별칭 테스트"""
    print("\n🩸 항응고제 별칭 테스트...")
    
    try:
        from app.models.request import RecommendationRequest, UserProfile, MedicationInfo
        from app.services.recommendation_engine import RecommendationEngine
        
        # 요청 생성 (MULTI:ANTICOAG 직접 사용)
        request = RecommendationRequest(
            intent_tags=["moisturizing", "anti-aging"],
            user_profile=UserProfile(
                age_group="30s",
                skin_type="dry"
            ),
            medications=[
                MedicationInfo(
                    name="항응고제",
                    active_ingredients=["MULTI:ANTICOAG"]
                )
            ],
            top_n=3
        )
        
        # 추천 엔진 실행
        engine = RecommendationEngine()
        response = await engine.recommend(request)
        
        print(f"✅ 항응고제 별칭 테스트 성공:")
        print(f"  - 배제된 제품: {response.pipeline_statistics.excluded_by_rules}개")
        print(f"  - 감점된 제품: {response.pipeline_statistics.penalized_products}개")
        print(f"  - 적용된 룰: {response.pipeline_statistics.eligibility_rules_applied + response.pipeline_statistics.scoring_rules_applied}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 항응고제 별칭 테스트 실패: {e}")
        return False

def test_rule_loading():
    """룰 로딩 테스트"""
    print("\n📋 룰 로딩 테스트...")
    
    try:
        from app.services.rule_service import RuleService
        
        rule_service = RuleService()
        
        # 배제 룰 확인
        eligibility_rules = rule_service.get_cached_eligibility_rules()
        print(f"✅ 배제 룰: {len(eligibility_rules)}개")
        
        # 감점 룰 확인
        scoring_rules = rule_service.get_cached_scoring_rules()
        print(f"✅ 감점 룰: {len(scoring_rules)}개")
        
        # 의약품 별칭 확인
        stats = rule_service.get_rule_statistics()
        print(f"✅ 룰 통계: {stats}")
        
        rule_service.close_session()
        return True
        
    except Exception as e:
        print(f"❌ 룰 로딩 실패: {e}")
        return False

def test_product_loading():
    """제품 데이터 로딩 테스트"""
    print("\n📦 제품 데이터 테스트...")
    
    try:
        from app.services.product_service import ProductService
        from app.models.request import RecommendationRequest
        
        product_service = ProductService()
        
        # 기본 요청으로 제품 조회
        request = RecommendationRequest(
            intent_tags=["moisturizing"],
            top_n=5
        )
        
        products = product_service.get_candidate_products(request, limit=100)
        print(f"✅ 제품 조회: {len(products)}개")
        
        # 샘플 제품 태그 확인
        if products:
            sample = products[0]
            print(f"✅ 샘플 제품: {sample.name} (태그: {len(sample.tags)}개)")
        
        return True
        
    except Exception as e:
        print(f"❌ 제품 데이터 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    print("🧪 추천 엔진 전체 플로우 테스트 시작\n")
    
    tests = [
        ("PostgreSQL 연결", lambda: __import__('test_postgres_connection').main() == 0),
        ("룰 로딩", test_rule_loading),
        ("제품 데이터", test_product_loading),
        ("기본 추천", test_basic_recommendation),
        ("의약품 추천", test_medication_recommendation),
        ("항응고제 별칭", test_anticoagulant_recommendation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name} 테스트...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name} 테스트 실패: {e}")
            results.append(False)
    
    # 결과 요약
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 테스트 결과 요약:")
    print(f"✅ 성공: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과! 배포 준비 완료")
        return 0
    else:
        print("\n⚠️  일부 테스트 실패. 문제 해결 후 재시도 필요")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))