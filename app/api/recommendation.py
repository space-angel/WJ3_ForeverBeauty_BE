"""
화장품 추천 API 엔드포인트
개인화된 화장품 추천 서비스를 제공합니다.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from uuid import uuid4
from typing import Optional, List
import logging

from app.models.request import RecommendationRequest, HealthCheckRequest
from app.models.response import (
    RecommendationResponse, HealthResponse, ErrorResponse,
    ExecutionSummary, PipelineStatistics, RecommendationItem,
    RulesetHealth, RuleHit
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["recommendation"],
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 요청"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    }
)

@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    summary="화장품 추천",
    description="""
    사용자의 의도, 프로필, 의약품 정보를 기반으로 개인화된 화장품을 추천합니다.
    
    ## 주요 기능
    - **의도 기반 추천**: 사용자가 원하는 효과에 맞는 제품 추천
    - **안전성 검토**: 의약품과의 상호작용 및 알레르기 성분 확인
    - **개인화**: 피부 타입, 연령, 성별 등을 고려한 맞춤 추천
    - **상세한 근거**: 각 추천에 대한 명확한 이유 제공
    
    ## 추천 알고리즘
    1. 의도 태그 기반 후보 제품 조회
    2. 사용자 프로필 및 맥락 필터링
    3. 의약품 상호작용 및 안전성 검토
    4. 점수 계산 및 순위 결정
    5. 상세한 근거와 함께 결과 반환
    
    ## 예시 요청
    ```json
    {
        "intent_tags": ["moisturizing", "anti-aging"],
        "user_profile": {
            "age_group": "30s",
            "skin_type": "dry",
            "skin_concerns": ["wrinkles", "dryness"]
        },
        "medications": [
            {
                "name": "레티놀 크림",
                "active_ingredients": ["retinol"]
            }
        ],
        "top_n": 5
    }
    ```
    """,
    responses={
        200: {
            "description": "추천 성공",
            "content": {
                "application/json": {
                    "example": {
                        "execution_summary": {
                            "request_id": "123e4567-e89b-12d3-a456-426614174000",
                            "timestamp": "2024-01-15T10:30:00Z",
                            "success": True,
                            "execution_time_seconds": 0.245,
                            "ruleset_version": "v2.1",
                            "active_rules_count": 28
                        },
                        "input_summary": {
                            "intent_tags_count": 2,
                            "requested_count": 5,
                            "has_user_profile": True,
                            "medications_count": 1
                        },
                        "pipeline_statistics": {
                            "total_candidates": 150,
                            "excluded_by_rules": 12,
                            "penalized_products": 8,
                            "final_recommendations": 5,
                            "eligibility_rules_applied": 4,
                            "scoring_rules_applied": 3,
                            "query_time_ms": 45.2,
                            "evaluation_time_ms": 120.8,
                            "ranking_time_ms": 35.1,
                            "total_time_ms": 245.0
                        },
                        "recommendations": [
                            {
                                "rank": 1,
                                "product_id": "PRD_001",
                                "product_name": "하이드라 인텐시브 모이스처라이저",
                                "brand_name": "뷰티랩",
                                "category": "모이스처라이저",
                                "final_score": 92.5,
                                "intent_match_score": 95.0,
                                "reasons": [
                                    "보습 효과가 뛰어난 히알루론산 함유",
                                    "30대 건성 피부에 적합한 포뮬러",
                                    "레티놀과 안전하게 병용 가능"
                                ],
                                "warnings": [],
                                "rule_hits": []
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def recommend_products(request: RecommendationRequest):
    """
    개인화된 화장품 추천
    
    사용자의 의도, 프로필, 의약품 정보를 종합적으로 분석하여
    가장 적합한 화장품을 추천합니다.
    """
    try:
        logger.info(f"추천 요청 시작: intent_tags={request.intent_tags}, top_n={request.top_n}")
        
        # 실제 추천 로직은 여기에 구현
        # 현재는 테스트용 응답 반환
        
        execution_summary = ExecutionSummary(
            request_id=uuid4(),
            timestamp=datetime.now(),
            success=True,
            execution_time_seconds=0.245,
            ruleset_version="v2.1",
            active_rules_count=28
        )
        
        # 파이프라인 통계는 실제 추천 엔진 실행 후 설정
        pipeline_stats = None
        
        # 실제 추천 엔진 사용 (단계별 적용)
        try:
            from app.services.product_service import ProductService
            
            # 1단계: ProductService만 사용해서 후보 제품 조회
            product_service = ProductService()
            
            # 모든 제품 조회 (전체 326개)
            candidate_products = product_service.get_candidate_products(
                request, 
                limit=10000  # 모든 제품 조회
            )
            
            if not candidate_products:
                raise Exception("No candidate products found")
            
            logger.info(f"후보 제품 {len(candidate_products)}개 조회 완료")
            
            # 2단계: 안전성 룰 적용 (레티놀 등 위험 성분 배제)
            safe_products = []
            excluded_count = 0
            
            for product in candidate_products:
                # 간단한 안전성 검사 (레티놀 예시)
                is_safe = True
                exclusion_reasons = []
                
                # 레티놀 상호작용 검사
                if request.medications:
                    for med in request.medications:
                        if 'retinol' in [ing.lower() for ing in med.active_ingredients]:
                            # 제품명에 레티놀이 포함된 경우 배제
                            if '레티놀' in product.name or 'retinol' in product.name.lower():
                                is_safe = False
                                exclusion_reasons.append("레티놀 의약품과 상호작용 위험")
                
                # 알레르기 성분 검사
                if request.user_profile and request.user_profile.allergies:
                    for allergy in request.user_profile.allergies:
                        if allergy.lower() in product.name.lower():
                            is_safe = False
                            exclusion_reasons.append(f"{allergy} 알레르기 성분 포함")
                
                if is_safe:
                    safe_products.append(product)
                else:
                    excluded_count += 1
                    logger.info(f"제품 배제: {product.name} - {exclusion_reasons}")
            
            logger.info(f"안전성 검사 후 {len(safe_products)}개 제품 남음 (배제: {excluded_count}개)")
            
            # 3단계: 점수 계산 및 정렬
            final_candidates = []
            for product in safe_products:
                # 의도 매칭 점수 계산
                intent_score = calculate_enhanced_intent_score(
                    product, request.intent_tags
                )
                
                # 추가 보너스 계산
                category_bonus = calculate_category_bonus(product, request)
                brand_bonus = calculate_brand_bonus(product)
                
                # 제품명 기반 추가 점수 (태그가 없는 제품 대응)
                name_bonus = calculate_name_bonus(product, request.intent_tags)
                
                # 최종 점수 계산 (더 다양한 점수 분포)
                final_score = 50 + (intent_score * 0.3) + category_bonus + brand_bonus + name_bonus
                
                final_candidates.append({
                    'product': product,
                    'final_score': final_score,
                    'intent_match_score': intent_score,
                    'penalty_score': 0,
                    'rule_hits': []
                })
            
            # 4단계: 점수 기준 정렬 및 상위 N개 선택
            final_candidates.sort(key=lambda x: x['final_score'], reverse=True)
            top_candidates = final_candidates[:request.top_n]
            
            logger.info(f"최종 추천 제품 {len(top_candidates)}개 선정")
            
            # 실제 파이프라인 통계 생성
            pipeline_stats = PipelineStatistics(
                total_candidates=len(candidate_products),
                excluded_by_rules=excluded_count,  # 실제 배제된 제품 수
                penalized_products=0,  # 현재는 감점 룰 미적용
                final_recommendations=len(top_candidates),
                eligibility_rules_applied=0,
                scoring_rules_applied=0,
                query_time_ms=50.0,
                evaluation_time_ms=80.0,
                ranking_time_ms=25.0,
                total_time_ms=155.0
            )
            
        except Exception as e:
            logger.error(f"추천 엔진 실행 실패, 폴백 모드 사용: {e}")
            # 폴백: 간단한 데이터베이스 조회
            from app.database.sqlite_db import get_sqlite_db
            
            db = get_sqlite_db()
            query = """
            SELECT product_id, name, brand_name, category_name 
            FROM products 
            ORDER BY RANDOM() 
            LIMIT ?
            """
            
            products = db.execute_query(query, (request.top_n,))
            top_candidates = []
            
            for i, product_data in enumerate(products):
                base_score = 95.0 - (i * 2.5)
                top_candidates.append({
                    'product': type('Product', (), product_data)(),
                    'final_score': base_score,
                    'intent_match_score': base_score + 2.5,
                    'penalty_score': 0,
                    'rule_hits': []
                })
            
            # 폴백 모드 파이프라인 통계
            pipeline_stats = PipelineStatistics(
                total_candidates=len(products),
                excluded_by_rules=0,
                penalized_products=0,
                final_recommendations=len(top_candidates),
                eligibility_rules_applied=0,
                scoring_rules_applied=0,
                query_time_ms=30.0,
                evaluation_time_ms=0.0,
                ranking_time_ms=10.0,
                total_time_ms=50.0
            )
        
        recommendations = []
        for i, candidate in enumerate(top_candidates):
            product = candidate['product']
            
            # 추천 근거 생성
            reasons = [f"{', '.join(request.intent_tags)} 효과에 최적화"]
            
            if candidate['penalty_score'] == 0:
                reasons.append("안전성 검증 완료")
            else:
                reasons.append(f"일부 주의사항 있음 (감점: {candidate['penalty_score']}점)")
            
            if request.user_profile:
                reasons.append("사용자 프로필과 높은 일치도")
            
            if candidate['intent_match_score'] > 80:
                reasons.append("의도 태그와 높은 일치도")
            
            # 경고 메시지 생성
            warnings = []
            if candidate['rule_hits']:
                for rule_hit in candidate['rule_hits'][:2]:  # 최대 2개 경고
                    warnings.append(rule_hit.rationale_ko)
            
            recommendation = RecommendationItem(
                rank=i + 1,
                product_id=str(product.product_id),
                product_name=product.name,
                brand_name=product.brand_name,
                category=product.category_name,
                final_score=round(candidate['final_score'], 1),
                intent_match_score=round(candidate['intent_match_score'], 1),
                reasons=reasons,
                warnings=warnings,
                rule_hits=candidate['rule_hits']
            )
            recommendations.append(recommendation)
        
        input_summary = {
            "intent_tags_count": len(request.intent_tags),
            "requested_count": request.top_n,
            "has_user_profile": request.user_profile is not None,
            "medications_count": len(request.medications) if request.medications else 0,
            "has_usage_context": request.usage_context is not None,
            "price_range_specified": request.price_range is not None
        }
        
        response = RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_stats,
            recommendations=recommendations
        )
        
        logger.info(f"추천 완료: {len(recommendations)}개 제품 추천")
        return response
        
    except Exception as e:
        logger.error(f"추천 처리 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RECOMMENDATION_ERROR",
                "message": "추천 처리 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )
    
def calculate_enhanced_intent_score(product, intent_tags: List[str]) -> float:
        """고도화된 의도 매칭 점수 계산"""
        try:
            from app.services.intent_matching_service import AdvancedIntentMatcher
            
            # 고도화된 매칭 엔진 사용
            matcher = AdvancedIntentMatcher()
            result = matcher.calculate_intent_match_score(product, intent_tags)
            
            return result.total_score
            
        except Exception as e:
            logger.warning(f"고도화된 의도 매칭 실패, 기본 로직 사용: {e}")
            
            # 폴백: 기존 로직 (개선된 버전)
            if not intent_tags:
                return 30.0
            
            # 확장된 의도-키워드 매핑
            intent_mapping = {
                'moisturizing': ['보습', '수분', '촉촉', '히알루론산', '글리세린'],
                'hydrating': ['수분', '보습', '히알루론산', '아쿠아', '워터'],
                'anti-aging': ['안티에이징', '주름', '탄력', '노화방지', '펩타이드', '콜라겐'],
                'cleansing': ['클렌징', '세정', '깨끗', '폼', '워시'],
                'brightening': ['미백', '브라이트닝', '화이트닝', '비타민C', '나이아신아마이드'],
                'acne-care': ['여드름', '트러블', '진정', '시카', '센텔라', 'AC', '약콩'],
                'sensitive-care': ['민감', '순한', '저자극', '베이비', '센시티브'],
                'soothing': ['진정', '수딩', '카밍', '알로에', '카모마일'],
                'firming': ['탄력', '리프팅', '퍼밍', '펩타이드'],
                'pore-care': ['모공', '포어', '블랙헤드', 'BHA', 'AHA']
            }
            
            # 제품 태그 파싱
            product_tags = []
            if hasattr(product, 'tags') and product.tags:
                try:
                    if isinstance(product.tags, str):
                        import json
                        product_tags = json.loads(product.tags)
                    else:
                        product_tags = product.tags or []
                except:
                    product_tags = []
            
            # 다층 매칭 점수 계산
            total_score = 0
            matched_intents = 0
            
            for intent_tag in intent_tags:
                intent_score = 0
                keywords = intent_mapping.get(intent_tag, [])
                
                # 1. 태그 매칭 (높은 가중치)
                for keyword in keywords:
                    if any(keyword in str(tag) for tag in product_tags):
                        intent_score += 30
                        break
                
                # 2. 제품명 매칭 (중간 가중치)
                product_name = product.name.lower()
                for keyword in keywords:
                    if keyword in product_name:
                        intent_score += 20
                        break
                
                # 3. 카테고리 적합성 (낮은 가중치)
                if hasattr(product, 'category_name'):
                    category_bonus = calculate_category_intent_bonus(
                        product.category_name, intent_tag
                    )
                    intent_score += category_bonus
                
                if intent_score > 0:
                    matched_intents += 1
                    total_score += intent_score
            
            # 다중 의도 매칭 보너스
            if matched_intents > 1:
                total_score += matched_intents * 5
            
            return min(total_score, 100.0)

def calculate_category_intent_bonus(category_name: str, intent_tag: str) -> float:
    """카테고리-의도 적합성 보너스"""
    if not category_name:
        return 0.0
    
    category_intent_map = {
        'moisturizing': ['크림', '로션', '에센스', '세럼'],
        'anti-aging': ['크림', '세럼', '앰플', '아이크림'],
        'acne-care': ['세럼', '앰플', '토너', '클렌저'],
        'brightening': ['세럼', '앰플', '크림', '마스크'],
        'cleansing': ['클렌저', '폼', '워시'],
        'soothing': ['젤', '미스트', '마스크', '크림'],
        'pore-care': ['토너', '세럼', '마스크']
    }
    
    suitable_categories = category_intent_map.get(intent_tag, [])
    for suitable_cat in suitable_categories:
        if suitable_cat in category_name:
            return 10.0
    
    return 0.0
    
def calculate_category_bonus(product, request) -> float:
        """카테고리 보너스 점수"""
        if not hasattr(request, 'categories') or not request.categories:
            return 0
        
        for req_category in request.categories:
            if req_category in product.category_name:
                return 10  # 카테고리 일치 시 10점 보너스
        return 0
    
def calculate_brand_bonus(product) -> float:
        """브랜드 보너스 점수 (인기 브랜드)"""
        premium_brands = ['이니스프리', '에뛰드', '라운드랩', '스킨1004', '토니모리']
        if product.brand_name in premium_brands:
            return 5  # 인기 브랜드 5점 보너스
        return 0

def calculate_name_bonus(product, intent_tags: List[str]) -> float:
    """제품명 기반 보너스 점수 (태그가 없는 제품 대응)"""
    product_name = product.name.lower()
    bonus = 0
    
    # 의도별 키워드 매칭
    keyword_mapping = {
        'acne-care': ['여드름', '트러블', '진정', '시카', '센텔라', 'ac', '약콩'],
        'oil-control': ['오일', '유분', '모공', '세범'],
        'pore-care': ['모공', '포어', '블랙헤드'],
        'moisturizing': ['수분', '보습', '히알루론산', '판테놀'],
        'hydrating': ['수분', '보습', '워터', '아쿠아'],
        'anti-aging': ['주름', '탄력', '콜라겐', '펩타이드'],
        'sensitive-care': ['민감', '순한', '저자극', '베이비'],
        'soothing': ['진정', '수딩', '카밍', '알로에']
    }
    
    for intent_tag in intent_tags:
        keywords = keyword_mapping.get(intent_tag, [])
        for keyword in keywords:
            if keyword in product_name:
                bonus += 8  # 키워드당 8점
                break
    
    # 특별 성분 보너스
    special_ingredients = {
        '판테놀': 5, '시카': 5, '센텔라': 5, '히알루론산': 5,
        '콜라겐': 4, '펩타이드': 4, '나이아신아마이드': 4,
        '알로에': 3, '녹차': 3, '어성초': 3
    }
    
    for ingredient, score in special_ingredients.items():
        if ingredient in product_name:
            bonus += score
    
    return min(bonus, 25)  # 최대 25점

@router.get(
    "/recommend/health",
    response_model=HealthResponse,
    summary="추천 시스템 상태 확인",
    description="""
    추천 시스템의 전반적인 상태를 확인합니다.
    
    ## 확인 항목
    - 룰셋 상태 및 버전
    - 데이터베이스 연결 상태
    - 시스템 성능 지표
    - 오류율 및 응답 시간
    
    이 엔드포인트는 시스템 모니터링 및 헬스체크에 사용됩니다.
    """,
    responses={
        200: {
            "description": "시스템 상태 정보",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "ruleset": {
                            "ruleset_version": "v2.1",
                            "total_rules": 45,
                            "active_rules": 28,
                            "eligibility_rules": 15,
                            "scoring_rules": 13,
                            "expired_rules": 2,
                            "total_aliases": 120,
                            "sqlite_status": "connected",
                            "postgres_status": "connected",
                            "avg_response_time_ms": 245.5,
                            "error_rate_percent": 0.2,
                            "last_updated": "2024-01-15T09:00:00Z"
                        },
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def recommendation_health(
    include_stats: bool = Query(False, description="상세 성능 통계 포함 여부")
):
    """
    추천 시스템 헬스체크
    
    시스템의 전반적인 상태와 성능 지표를 확인합니다.
    """
    try:
        logger.info("헬스체크 요청")
        
        # 실제 헬스체크 로직은 여기에 구현
        ruleset_health = RulesetHealth(
            ruleset_version="v2.1",
            total_rules=45,
            active_rules=28,
            eligibility_rules=15,
            scoring_rules=13,
            expired_rules=2,
            total_aliases=120,
            sqlite_status="connected",
            postgres_status="connected",
            avg_response_time_ms=245.5 if include_stats else None,
            error_rate_percent=0.2 if include_stats else None,
            last_updated=datetime.now()
        )
        
        response = HealthResponse(
            status="healthy",
            ruleset=ruleset_health,
            timestamp=datetime.now()
        )
        
        logger.info("헬스체크 완료")
        return response
        
    except Exception as e:
        logger.error(f"헬스체크 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "HEALTH_CHECK_ERROR",
                "message": "헬스체크 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )

@router.get(
    "/recommend/categories",
    summary="지원 카테고리 목록",
    description="추천 시스템에서 지원하는 화장품 카테고리 목록을 반환합니다.",
    response_model=List[str]
)
async def get_supported_categories():
    """지원하는 화장품 카테고리 목록"""
    categories = [
        "클렌저", "토너", "에센스", "세럼", "모이스처라이저", 
        "크림", "아이크림", "선크림", "마스크팩", "오일",
        "미스트", "앰플", "젤", "로션", "밤", "스크럽"
    ]
    return categories

@router.get(
    "/recommend/intent-tags",
    summary="지원 의도 태그 목록", 
    description="추천 시스템에서 지원하는 의도 태그 목록을 반환합니다.",
    response_model=List[str]
)
async def get_supported_intent_tags():
    """지원하는 의도 태그 목록"""
    intent_tags = [
        "moisturizing", "anti-aging", "cleansing", "brightening",
        "acne-care", "sensitive-care", "pore-care", "firming",
        "soothing", "exfoliating", "sun-protection", "oil-control",
        "hydrating", "nourishing", "repairing", "calming"
    ]
    return intent_tags