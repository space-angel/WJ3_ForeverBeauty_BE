#!/usr/bin/env python3
"""
룰 적용 실패 원인 심층 분석
각 단계별로 상세하게 디버깅합니다.
"""
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def deep_debug_rules():
    """룰 적용 과정을 매우 상세하게 디버깅"""
    print("🔬 룰 적용 심층 분석 시작...\n")
    
    try:
        from app.models.request import RecommendationRequest, UserProfile, MedicationInfo
        from app.services.recommendation_engine import RecommendationEngine
        from app.services.rule_service import RuleService
        from app.services.eligibility_engine import EligibilityEngine
        from app.services.scoring_engine import ScoringEngine
        from app.services.product_service import ProductService
        from uuid import uuid4
        
        # 1. AHA 태그가 있는 제품 찾기
        product_service = ProductService()
        request = RecommendationRequest(intent_tags=['moisturizing'], top_n=20)
        all_products = product_service.get_candidate_products(request, limit=1000)
        
        aha_products = [p for p in all_products if any('aha' in tag.lower() for tag in p.tags)]
        print(f"1️⃣ AHA 관련 제품: {len(aha_products)}개")
        
        if not aha_products:
            print("❌ AHA 제품이 없습니다!")
            return
        
        sample_product = aha_products[0]
        print(f"   샘플 제품: {sample_product.name} (ID: {sample_product.product_id})")
        print(f"   제품 태그: {sample_product.tags}")
        
        # 2. 테스트 요청 생성
        test_request = RecommendationRequest(
            intent_tags=['moisturizing'],
            medications=[MedicationInfo(name='와파린', active_ingredients=['B01AA03'])],
            top_n=1
        )
        
        # 3. 요청 전처리
        engine = RecommendationEngine()
        engine._preprocess_request(test_request)
        
        print(f"\n2️⃣ 전처리된 요청:")
        print(f"   med_profile.codes: {test_request.med_profile.codes}")
        
        # 4. 의약품 코드 해석
        rule_service = RuleService()
        resolved = rule_service.resolve_med_codes_batch(test_request.med_profile.codes)
        all_med_codes = set()
        for codes in resolved.values():
            all_med_codes.update(codes)
        
        print(f"\n3️⃣ 의약품 코드 해석:")
        print(f"   모든 의약품 코드: {all_med_codes}")
        
        # 5. 감점 룰 확인
        scoring_rules = rule_service.get_cached_scoring_rules()
        print(f"\n4️⃣ 감점 룰 분석:")
        print(f"   전체 감점 룰: {len(scoring_rules)}개")
        
        # 관련 룰 찾기
        relevant_rules = []
        for rule in scoring_rules:
            if rule.get('med_code') in all_med_codes:
                relevant_rules.append(rule)
        
        print(f"   관련 감점 룰: {len(relevant_rules)}개")
        for rule in relevant_rules:
            print(f"     - {rule['rule_id']}: {rule['med_code']} + {rule['ingredient_tag']}")
        
        # 6. 제품 태그와 룰 매칭 테스트
        print(f"\n5️⃣ 태그 매칭 테스트:")
        product_tags = sample_product.tags
        normalized_product_tags = set(tag.lower().strip() for tag in product_tags)
        print(f"   제품 태그 (정규화): {normalized_product_tags}")
        
        matching_rules = []
        for rule in relevant_rules:
            rule_tag = rule['ingredient_tag'].lower().strip()
            print(f"\n   룰 태그 '{rule_tag}' 매칭 테스트:")
            
            # 정확한 매칭
            if rule_tag in normalized_product_tags:
                print(f"     ✅ 정확한 매칭 발견!")
                matching_rules.append(rule)
                continue
            
            # 부분 매칭
            partial_matches = []
            for product_tag in normalized_product_tags:
                if rule_tag in product_tag or product_tag in rule_tag:
                    partial_matches.append(product_tag)
            
            if partial_matches:
                print(f"     ✅ 부분 매칭 발견: {partial_matches}")
                matching_rules.append(rule)
            else:
                print(f"     ❌ 매칭 없음")
        
        print(f"\n   최종 매칭된 룰: {len(matching_rules)}개")
        
        # 7. 감점 엔진 직접 테스트
        print(f"\n6️⃣ 감점 엔진 직접 테스트:")
        scoring_engine = ScoringEngine()
        
        try:
            result = scoring_engine.evaluate_products([sample_product], test_request, uuid4())
            print(f"   감점 엔진 실행 성공!")
            print(f"   결과 타입: {type(result)}")
            print(f"   결과 내용: {result}")
            
        except Exception as e:
            print(f"   ❌ 감점 엔진 실행 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # 8. 전체 추천 엔진 테스트
        print(f"\n7️⃣ 전체 추천 엔진 테스트:")
        try:
            response = await engine.recommend(test_request)
            print(f"   실행 성공!")
            print(f"   감점 룰 적용: {response.pipeline_statistics.scoring_rules_applied}개")
            print(f"   감점된 제품: {response.pipeline_statistics.penalized_products}개")
            
        except Exception as e:
            print(f"   ❌ 추천 엔진 실행 실패: {e}")
            import traceback
            traceback.print_exc()
        
        rule_service.close_session()
        
    except Exception as e:
        print(f"❌ 심층 분석 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(deep_debug_rules())