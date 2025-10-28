#!/usr/bin/env python3
"""
룰 매칭 디버깅 스크립트
왜 룰이 적용되지 않는지 단계별로 확인합니다.
"""
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def debug_rule_matching():
    """룰 매칭 과정을 단계별로 디버깅"""
    print("🔍 룰 매칭 디버깅 시작...\n")
    
    try:
        from app.models.request import RecommendationRequest, UserProfile, MedicationInfo
        from app.services.recommendation_engine import RecommendationEngine
        from app.services.rule_service import RuleService
        from app.services.eligibility_engine import EligibilityEngine
        from app.services.scoring_engine import ScoringEngine
        from app.services.product_service import ProductService
        
        # 1. 요청 생성
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
        
        print("1️⃣ 요청 정보:")
        print(f"  - 의도 태그: {request.intent_tags}")
        print(f"  - 의약품: {[m.name for m in request.medications]}")
        print(f"  - 의약품 코드: {[code for m in request.medications for code in m.active_ingredients]}")
        
        # 2. 요청 전처리 확인
        engine = RecommendationEngine()
        engine._preprocess_request(request)
        
        print(f"\n2️⃣ 전처리 후:")
        if request.med_profile:
            print(f"  - med_profile.codes: {request.med_profile.codes}")
        else:
            print("  - med_profile: None")
        
        # 3. 의약품 코드 해석 확인
        rule_service = RuleService()
        if request.med_profile:
            resolved = rule_service.resolve_med_codes_batch(request.med_profile.codes)
            print(f"\n3️⃣ 의약품 코드 해석:")
            for original, resolved_codes in resolved.items():
                print(f"  - {original} → {resolved_codes}")
        
        # 4. 룰 확인
        eligibility_rules = rule_service.get_cached_eligibility_rules()
        scoring_rules = rule_service.get_cached_scoring_rules()
        
        print(f"\n4️⃣ 로딩된 룰:")
        print(f"  - 배제 룰: {len(eligibility_rules)}개")
        print(f"  - 감점 룰: {len(scoring_rules)}개")
        
        # 5. 관련 룰 찾기
        if request.med_profile:
            all_med_codes = set()
            resolved = rule_service.resolve_med_codes_batch(request.med_profile.codes)
            for codes in resolved.values():
                all_med_codes.update(codes)
            
            print(f"\n5️⃣ 모든 의약품 코드: {all_med_codes}")
            
            # 매칭되는 배제 룰 찾기
            matching_eligibility = []
            for rule in eligibility_rules:
                if rule.get('med_code') in all_med_codes:
                    matching_eligibility.append(rule)
            
            print(f"\n6️⃣ 매칭되는 배제 룰: {len(matching_eligibility)}개")
            for rule in matching_eligibility:
                print(f"  - {rule['rule_id']}: {rule['med_code']} + {rule['ingredient_tag']}")
            
            # 매칭되는 감점 룰 찾기
            matching_scoring = []
            for rule in scoring_rules:
                if rule.get('med_code') in all_med_codes:
                    matching_scoring.append(rule)
            
            print(f"\n7️⃣ 매칭되는 감점 룰: {len(matching_scoring)}개")
            for rule in matching_scoring:
                print(f"  - {rule['rule_id']}: {rule['med_code']} + {rule['ingredient_tag']}")
        
        # 6. 제품 데이터 확인
        product_service = ProductService()
        products = product_service.get_candidate_products(request, limit=10)
        
        print(f"\n8️⃣ 샘플 제품 태그:")
        for i, product in enumerate(products[:3]):
            print(f"  - {product.name[:30]}...: {product.tags[:5]}...")
        
        # 7. 실제 엔진 실행
        print(f"\n9️⃣ 실제 추천 엔진 실행...")
        response = await engine.recommend(request)
        
        print(f"  - 배제된 제품: {response.pipeline_statistics.excluded_by_rules}개")
        print(f"  - 감점된 제품: {response.pipeline_statistics.penalized_products}개")
        print(f"  - 적용된 배제 룰: {response.pipeline_statistics.eligibility_rules_applied}개")
        print(f"  - 적용된 감점 룰: {response.pipeline_statistics.scoring_rules_applied}개")
        
        rule_service.close_session()
        
    except Exception as e:
        print(f"❌ 디버깅 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_rule_matching())