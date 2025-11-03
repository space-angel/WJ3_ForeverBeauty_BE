"""
다차원 점수 계산 엔진
의도, 개인화, 안전성 점수를 통합하여 최종 점수를 계산하는 시스템
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging
import json
import re
from collections import defaultdict
import asyncio

from app.models.personalization_models import (
    ProductScore, ScoreBreakdown, PersonalizedRecommendation,
    ProductIngredientAnalysis, ProfileMatchResult,
    ScoreCalculationError, SafetyLevel
)
from app.models.postgres_models import Product

logger = logging.getLogger(__name__)

@dataclass
class IntentMatchResult:
    """의도 매칭 결과"""
    product_id: int
    intent_score: float
    matched_tags: List[str] = field(default_factory=list)
    matched_attributes: List[str] = field(default_factory=list)
    match_rationales: List[str] = field(default_factory=list)

@dataclass
class SafetyAssessment:
    """안전성 평가 결과"""
    product_id: int
    safety_score: float
    safety_level: SafetyLevel
    risk_factors: List[str] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)
    age_restrictions: List[str] = field(default_factory=list)

class IntentScorer:
    """의도 매칭 점수 계산기"""
    
    def __init__(self):
        # 의도별 키워드 매핑 (영어-한국어 통합)
        self.intent_keywords = {
            # 영어 의도 태그 (실제 DB 태그 기반)
            "moisturizing": ["보습", "수분", "수분보유", "수분공급", "hyaluronic_acid", "히알루론산", "글리세린", "세라마이드", "스쿠알란"],
            "whitening": ["미백", "브라이트닝", "비타민C", "나이아신아마이드", "알부틴", "코직산"],
            "anti-aging": ["안티에이징", "주름개선", "retinoid", "retinoid_family", "레티놀", "펩타이드", "콜라겐", "아데노신"],
            "sensitive-care": ["진정", "민감케어", "상처치유", "장벽강화", "수딩", "알로에", "센텔라", "판테놀", "카모마일"],
            "exfoliating": ["각질", "필링", "AHA", "BHA", "살리실산", "글리콜산", "peel", "exfoliat"],
            "oil-control": ["피지", "오일컨트롤", "수렴", "티트리", "클레이", "숯", "sebum", "pore"],
            "pore-care": ["모공", "포어", "수렴", "나이아신아마이드", "레티놀", "pore", "tighten"],
            "acne-care": ["트러블", "여드름", "아크네", "살리실산", "벤조일퍼옥사이드", "acne", "blemish"],
            "sun-protection": ["자외선", "SPF", "PA", "선크림", "선블록", "sunscreen", "uv"],
            "firming": ["탄력", "리프팅", "펩타이드", "콜라겐", "DMAE", "firm", "lift", "elastic"],
            
            # 한국어 의도 태그 (기존 호환성)
            "보습": ["보습", "수분", "히알루론산", "글리세린", "세라마이드", "스쿠알란"],
            "미백": ["미백", "브라이트닝", "비타민C", "나이아신아마이드", "알부틴", "코직산"],
            "주름개선": ["주름", "안티에이징", "레티놀", "펩타이드", "콜라겐", "아데노신"],
            "진정": ["진정", "수딩", "알로에", "센텔라", "판테놀", "카모마일"],
            "각질제거": ["각질", "필링", "AHA", "BHA", "살리실산", "글리콜산"],
            "피지조절": ["피지", "오일컨트롤", "수렴", "티트리", "클레이", "숯"],
            "모공관리": ["모공", "포어", "수렴", "나이아신아마이드", "레티놀"],
            "트러블케어": ["트러블", "여드름", "아크네", "살리실산", "벤조일퍼옥사이드"],
            "자외선차단": ["자외선", "SPF", "PA", "선크림", "선블록"],
            "탄력": ["탄력", "리프팅", "펩타이드", "콜라겐", "DMAE"]
        }
        
        # 카테고리별 가중치
        self.category_weights = {
            "스킨케어": 1.0,
            "클렌징": 0.9,
            "마스크": 0.8,
            "선케어": 1.1,
            "메이크업": 0.7
        }
    
    async def calculate_intent_score(
        self, 
        product: Product, 
        intent_tags: List[str]
    ) -> IntentMatchResult:
        """의도 매칭 점수 계산"""
        try:
            if not intent_tags:
                return IntentMatchResult(
                    product_id=product.product_id,
                    intent_score=50.0,
                    match_rationales=["의도 정보가 없습니다"]
                )
            
            total_score = 0.0
            matched_tags = []
            matched_attributes = []
            rationales = []
            
            # 1. 제품 태그와 의도 매칭
            tag_score = self._match_product_tags(product, intent_tags, matched_tags, rationales)
            
            # 2. 제품 속성과 의도 매칭
            attr_score = self._match_product_attributes(product, intent_tags, matched_attributes, rationales)
            
            # 3. 카테고리 가중치 적용
            category_weight = self.category_weights.get(product.category_name, 1.0)
            
            # 최종 점수 계산 (태그 70% + 속성 30%)
            base_score = (tag_score * 0.7) + (attr_score * 0.3)
            final_score = base_score * category_weight
            
            # 점수 정규화 (0-100)
            final_score = max(0.0, min(100.0, final_score))
            
            return IntentMatchResult(
                product_id=product.product_id,
                intent_score=final_score,
                matched_tags=matched_tags,
                matched_attributes=matched_attributes,
                match_rationales=rationales[:3]  # 상위 3개 근거
            )
            
        except Exception as e:
            logger.error(f"의도 점수 계산 실패 (product_id: {product.product_id}): {e}")
            raise ScoreCalculationError(f"의도 점수 계산 실패: {e}")
    
    def _match_product_tags(
        self, 
        product: Product, 
        intent_tags: List[str], 
        matched_tags: List[str], 
        rationales: List[str]
    ) -> float:
        """제품 태그와 의도 매칭"""
        if not product.tags:
            return 30.0  # 기본 점수
        
        score = 30.0
        product_tags = [tag.lower() for tag in product.tags]
        
        for intent in intent_tags:
            intent_lower = intent.lower()
            intent_keywords = self.intent_keywords.get(intent, [intent])
            
            # 직접 매칭
            if intent_lower in product_tags:
                score += 25
                matched_tags.append(intent)
                rationales.append(f"'{intent}' 의도와 직접 매칭")
                continue
            
            # 키워드 매칭
            for keyword in intent_keywords:
                keyword_lower = keyword.lower()
                for tag in product_tags:
                    if keyword_lower in tag or self._fuzzy_match(keyword_lower, tag):
                        score += 15
                        matched_tags.append(keyword)
                        rationales.append(f"'{intent}' 의도와 '{keyword}' 키워드 매칭")
                        break
        
        return min(100.0, score)
    
    def _match_product_attributes(
        self, 
        product: Product, 
        intent_tags: List[str], 
        matched_attributes: List[str], 
        rationales: List[str]
    ) -> float:
        """제품 속성과 의도 매칭"""
        score = 30.0
        
        if product.primary_attr:
            primary_attr_lower = product.primary_attr.lower()
            
            for intent in intent_tags:
                intent_keywords = self.intent_keywords.get(intent, [intent])
                
                for keyword in intent_keywords:
                    if keyword.lower() in primary_attr_lower:
                        score += 20
                        matched_attributes.append(keyword)
                        rationales.append(f"주요 속성에서 '{keyword}' 매칭")
                        break
        
        return min(100.0, score)
    
    def _fuzzy_match(self, keyword: str, tag: str, threshold: float = 0.7) -> bool:
        """퍼지 매칭 (유사도 기반)"""
        # 간단한 부분 문자열 매칭
        if len(keyword) >= 2 and keyword in tag:
            return True
        
        # 편집 거리 기반 유사도 (간단 구현)
        if len(keyword) >= 3 and len(tag) >= 3:
            common_chars = set(keyword) & set(tag)
            similarity = len(common_chars) / max(len(set(keyword)), len(set(tag)))
            return similarity >= threshold
        
        return False

class SafetyScorer:
    """안전성 점수 계산기"""
    
    def __init__(self):
        # EWG 등급별 점수 매핑
        self.ewg_scores = {
            "1": 100, "1_2": 95, "2": 90, "2_3": 85, "3": 80,
            "4": 70, "5": 60, "6": 50, "7": 40, "8": 30, "9": 20, "10": 10,
            "unknown": 60
        }
        
        # 연령별 위험 성분
        self.age_risk_ingredients = {
            "10s": ["레티놀", "고농도산", "강한화학성분"],
            "20s": ["고농도레티놀", "강한필링성분"],
            "30s": ["과도한자극성분"],
            "40s": ["알코올", "강한방부제"],
            "50s": ["자극성분", "알코올", "인공향료", "강한계면활성제"]
        }
        
        # 피부타입별 위험 성분
        self.skin_type_risks = {
            "sensitive": ["향료", "알코올", "자극성분", "산성분"],
            "dry": ["알코올", "강한계면활성제", "건조성분"],
            "oily": ["과도한유분", "코메도제닉"],
            "combination": ["극단적성분"]
        }
    
    async def calculate_safety_score(
        self, 
        product: Product, 
        ingredient_analysis: Optional[ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> SafetyAssessment:
        """안전성 점수 계산"""
        try:
            base_score = 80.0  # 기본 안전성 점수
            risk_factors = []
            warnings = []
            age_restrictions = []
            
            # 1. 성분 분석 기반 안전성 평가
            if ingredient_analysis:
                ingredient_score = self._assess_ingredient_safety(
                    ingredient_analysis, risk_factors, warnings
                )
                base_score = min(base_score, ingredient_score)
            
            # 2. 사용자 프로필 기반 위험도 평가
            if user_profile:
                profile_penalty = self._assess_profile_risks(
                    product, user_profile, risk_factors, warnings, age_restrictions
                )
                base_score -= profile_penalty
            
            # 3. 제품 태그 기반 안전성 검사
            tag_penalty = self._assess_tag_safety(product, risk_factors, warnings)
            base_score -= tag_penalty
            
            # 최종 점수 정규화
            final_score = max(0.0, min(100.0, base_score))
            
            # 안전성 수준 결정
            safety_level = self._determine_safety_level(final_score, risk_factors)
            
            return SafetyAssessment(
                product_id=product.product_id,
                safety_score=final_score,
                safety_level=safety_level,
                risk_factors=risk_factors,
                safety_warnings=warnings,
                age_restrictions=age_restrictions
            )
            
        except Exception as e:
            logger.error(f"안전성 점수 계산 실패 (product_id: {product.product_id}): {e}")
            raise ScoreCalculationError(f"안전성 점수 계산 실패: {e}")
    
    def _assess_ingredient_safety(
        self, 
        analysis: ProductIngredientAnalysis, 
        risk_factors: List[str], 
        warnings: List[str]
    ) -> float:
        """성분 분석 기반 안전성 평가"""
        score = 80.0
        
        # 유해 효과 감점
        for effect in analysis.harmful_effects:
            penalty = abs(effect.weighted_score) * 0.1
            score -= penalty
            risk_factors.append(f"{effect.ingredient_name}: {effect.effect_description}")
        
        # 안전성 경고 감점
        for warning in analysis.safety_warnings:
            score -= 5
            warnings.append(warning)
        
        # 알레르기 위험 감점
        for allergy in analysis.allergy_risks:
            score -= 8
            risk_factors.append(f"알레르기 위험: {allergy}")
        
        return max(0.0, score)
    
    def _assess_profile_risks(
        self, 
        product: Product, 
        user_profile: Dict[str, Any], 
        risk_factors: List[str], 
        warnings: List[str], 
        age_restrictions: List[str]
    ) -> float:
        """사용자 프로필 기반 위험도 평가"""
        penalty = 0.0
        
        age_group = user_profile.get('age_group')
        skin_type = user_profile.get('skin_type')
        
        # 연령별 위험 성분 검사
        if age_group and age_group in self.age_risk_ingredients:
            risk_ingredients = self.age_risk_ingredients[age_group]
            for tag in product.tags:
                for risk_ingredient in risk_ingredients:
                    if risk_ingredient in tag:
                        penalty += 10
                        age_restrictions.append(f"{age_group}에 부적합: {risk_ingredient}")
        
        # 피부타입별 위험 성분 검사
        if skin_type and skin_type in self.skin_type_risks:
            risk_ingredients = self.skin_type_risks[skin_type]
            for tag in product.tags:
                for risk_ingredient in risk_ingredients:
                    if risk_ingredient in tag:
                        penalty += 8
                        warnings.append(f"{skin_type} 피부에 주의: {risk_ingredient}")
        
        return penalty
    
    def _assess_tag_safety(
        self, 
        product: Product, 
        risk_factors: List[str], 
        warnings: List[str]
    ) -> float:
        """제품 태그 기반 안전성 검사"""
        penalty = 0.0
        
        # 위험 키워드 검사
        danger_keywords = ["자극", "알코올", "파라벤", "황산", "인공색소"]
        
        for tag in product.tags:
            tag_lower = tag.lower()
            for keyword in danger_keywords:
                if keyword in tag_lower:
                    penalty += 3
                    warnings.append(f"주의 성분 포함: {keyword}")
        
        return penalty
    
    def _determine_safety_level(self, score: float, risk_factors: List[str]) -> SafetyLevel:
        """안전성 수준 결정"""
        if score >= 80 and len(risk_factors) == 0:
            return SafetyLevel.SAFE
        elif score >= 60 and len(risk_factors) <= 2:
            return SafetyLevel.CAUTION
        elif score >= 40:
            return SafetyLevel.WARNING
        else:
            return SafetyLevel.DANGER

class ScoreCalculator:
    """다차원 점수 계산 엔진"""
    
    def __init__(self):
        self.intent_scorer = IntentScorer()
        self.safety_scorer = SafetyScorer()
        
        # 기본 가중치 (합계 100%)
        self.default_weights = {
            'intent': 30.0,
            'personalization': 40.0,
            'safety': 30.0
        }
    
    def evaluate_products(self, products: List[Product], request, request_id) -> Dict[int, Dict[str, Any]]:
        """제품 평가 (recommendation_engine 호환용) - 개인화 + 의약품 룰 적용"""
        logger.info(f"🚀 스코어링 엔진 시작: {len(products)}개 제품 평가")
        results = {}
        
        # 의약품 기반 감점 룰 적용을 위한 준비
        rule_penalties = self._apply_medication_scoring_rules(products, request)
        logger.info(f"💊 의약품 룰 적용 결과: {len(rule_penalties)}개 제품에 감점")
        
        for product in products:
            # 1. 기본 점수
            base_score = 100
            penalty_score = 0
            rule_hits = []
            
            # 2. 의도 일치도 계산 (개선된 버전)
            intent_score = self._calculate_intent_match_score(product, request)
            
            # 3. 개인화 점수 계산
            personalization_score = self._calculate_personalization_score(product, request)
            
            # 4. 안전성 감점 계산 (사용자 프로필 기반)
            safety_penalty = self._calculate_safety_penalty(product, request)
            penalty_score += safety_penalty
            
            # 5. 의약품 기반 감점 룰 적용
            if product.product_id in rule_penalties:
                med_penalty_info = rule_penalties[product.product_id]
                med_penalty = med_penalty_info['total_penalty']
                penalty_score += med_penalty
                rule_hits.extend(med_penalty_info['rule_hits'])
            
            # 6. 최종 점수 계산 (가중 평균)
            final_score = (
                intent_score * 0.4 +           # 의도 일치 40%
                personalization_score * 0.4 +  # 개인화 40%
                (100 - penalty_score) * 0.2    # 안전성 20% (총 감점 적용)
            )
            
            final_score = max(final_score, 0)
            
            results[product.product_id] = {
                'final_score': final_score,
                'base_score': base_score,
                'penalty_score': penalty_score,
                'intent_match_score': intent_score,
                'personalization_score': personalization_score,
                'safety_penalty': safety_penalty,
                'medication_penalty': rule_penalties.get(product.product_id, {}).get('total_penalty', 0),
                'rule_hits': rule_hits
            }
            
            # 상세 로그 (처음 3개 제품만)
            if len(results) <= 3:
                logger.info(f"📊 제품 {product.product_id} ({product.name[:20]}...): "
                          f"최종점수={final_score:.1f}, 의도={intent_score:.1f}, "
                          f"개인화={personalization_score:.1f}, 안전성감점={safety_penalty:.1f}, "
                          f"의약품감점={rule_penalties.get(product.product_id, {}).get('total_penalty', 0):.1f}, "
                          f"룰적용={len(rule_hits)}개")
        
        return results
    
    def _calculate_intent_match_score(self, product: Product, request) -> float:
        """의도 일치도 점수 계산 (개선된 버전)"""
        if not hasattr(request, 'intent_tags') or not request.intent_tags:
            return 50.0
        
        product_tags = product.tags if product.tags else []
        product_name = product.name.lower() if product.name else ""
        
        if not product_tags and not product_name:
            return 30.0
        
        # 제품 태그 정규화
        normalized_product_tags = [tag.lower().strip() for tag in product_tags]
        
        # 의도별 매칭 점수 계산
        intent_scores = []
        matched_details = []
        
        for intent in request.intent_tags:
            intent_lower = intent.lower().strip()
            intent_score = 0
            match_reason = ""
            
            # 1. 직접 매칭 (최고 점수)
            if intent_lower in normalized_product_tags:
                intent_score = 100
                match_reason = f"태그 직접 매칭: {intent_lower}"
            elif intent_lower in product_name:
                intent_score = 95
                match_reason = f"제품명 직접 매칭: {intent_lower}"
            else:
                # 2. 키워드 매핑 매칭
                intent_keywords = self.intent_scorer.intent_keywords.get(intent_lower, [intent_lower])
                best_match_score = 0
                best_match_reason = ""
                
                for keyword in intent_keywords:
                    keyword_lower = keyword.lower()
                    
                    # 태그에서 키워드 검색
                    for tag in normalized_product_tags:
                        if keyword_lower == tag:
                            # 완전 일치
                            if 90 > best_match_score:
                                best_match_score = 90
                                best_match_reason = f"태그 완전 매칭: {keyword_lower}"
                        elif keyword_lower in tag:
                            # 부분 일치 (키워드가 태그에 포함)
                            if 70 > best_match_score:
                                best_match_score = 70
                                best_match_reason = f"태그 부분 매칭: {keyword_lower} in {tag}"
                        elif tag in keyword_lower and len(tag) >= 2:
                            # 역방향 부분 일치 (태그가 키워드에 포함)
                            if 60 > best_match_score:
                                best_match_score = 60
                                best_match_reason = f"태그 역방향 매칭: {tag} in {keyword_lower}"
                    
                    # 제품명에서 키워드 검색
                    if keyword_lower in product_name:
                        if 75 > best_match_score:
                            best_match_score = 75
                            best_match_reason = f"제품명 키워드 매칭: {keyword_lower}"
                
                intent_score = best_match_score
                match_reason = best_match_reason
            
            # 매칭되지 않은 경우 기본 점수
            if intent_score == 0:
                intent_score = 20
                match_reason = f"매칭 없음: {intent_lower}"
            
            intent_scores.append(intent_score)
            matched_details.append(f"{intent_lower}={intent_score:.0f}({match_reason[:30]})")
        
        # 가중 평균 계산 (모든 의도가 중요)
        final_score = sum(intent_scores) / len(intent_scores)
        
        # 매칭 품질에 따른 보너스/페널티
        perfect_matches = sum(1 for score in intent_scores if score >= 90)
        good_matches = sum(1 for score in intent_scores if 70 <= score < 90)
        poor_matches = sum(1 for score in intent_scores if score < 50)
        
        # 보너스: 완벽한 매칭이 많을수록
        if perfect_matches == len(intent_scores):
            final_score = min(final_score + 5, 100)
        elif perfect_matches > len(intent_scores) / 2:
            final_score = min(final_score + 3, 100)
        
        # 페널티: 매칭이 부족할수록
        if poor_matches > len(intent_scores) / 2:
            final_score = max(final_score - 10, 20)
        
        # 디버그 로그 (처음 5개 제품만)
        if len(matched_details) <= 5:
            logger.info(f"🎯 제품 {product.product_id} 의도 매칭: {'; '.join(matched_details)} → {final_score:.1f}")
            logger.info(f"   제품 태그: {normalized_product_tags[:5]}...")  # 처음 5개 태그만
        
        return round(final_score, 1)
    
    def _calculate_personalization_score(self, product: Product, request) -> float:
        """개인화 점수 계산"""
        if not hasattr(request, 'user_profile') or not request.user_profile:
            return 70.0  # 프로필 없으면 중간 점수
        
        profile = request.user_profile
        score = 70.0  # 기본 점수
        score_details = []
        
        # 연령대별 점수 조정
        if hasattr(profile, 'age_group') and profile.age_group:
            age_bonus = self._get_age_compatibility_score(product, profile.age_group)
            score += age_bonus
            score_details.append(f"연령({profile.age_group})={age_bonus:+.1f}")
        
        # 피부타입별 점수 조정
        if hasattr(profile, 'skin_type') and profile.skin_type:
            skin_bonus = self._get_skin_type_compatibility_score(product, profile.skin_type)
            score += skin_bonus
            score_details.append(f"피부타입({profile.skin_type})={skin_bonus:+.1f}")
        
        # 피부 고민별 점수 조정
        if hasattr(profile, 'skin_concerns') and profile.skin_concerns:
            concern_bonus = self._get_skin_concern_compatibility_score(product, profile.skin_concerns)
            score += concern_bonus
            score_details.append(f"피부고민={concern_bonus:+.1f}")
        
        final_score = min(score, 100.0)
        
        # 디버그 로그 (처음 3개 제품만)
        if len(score_details) <= 3:
            logger.debug(f"👤 제품 {product.product_id} 개인화: 기본70 + {'; '.join(score_details)} → {final_score:.1f}")
        
        return final_score
    
    def _apply_medication_scoring_rules(self, products: List[Product], request) -> Dict[int, Dict[str, Any]]:
        """의약품 기반 감점 룰 적용"""
        from app.services.rule_service import RuleService
        
        rule_service = RuleService()
        penalties = {}
        
        try:
            # 의약품 코드 추출 (개선된 로직)
            med_codes = []
            
            # 1. medications 필드에서 추출
            if hasattr(request, 'medications') and request.medications:
                logger.info(f"🔍 medications 필드 발견: {len(request.medications)}개")
                for med in request.medications:
                    if hasattr(med, 'active_ingredients') and med.active_ingredients:
                        med_codes.extend(med.active_ingredients)
                        logger.info(f"  📋 의약품 '{med.name}': {med.active_ingredients}")
            
            # 2. med_profile 필드에서 추출 (호환성)
            if hasattr(request, 'med_profile') and request.med_profile:
                if hasattr(request.med_profile, 'codes') and request.med_profile.codes:
                    med_codes.extend(request.med_profile.codes)
                    logger.info(f"  📋 med_profile.codes: {request.med_profile.codes}")
            
            # 중복 제거
            med_codes = list(set(med_codes))
            
            if not med_codes:
                logger.info("💊 의약품 코드가 없어 감점 룰 적용 건너뜀")
                logger.info(f"  🔍 request 속성: {[attr for attr in dir(request) if not attr.startswith('_')]}")
                return penalties
            
            logger.info(f"💊 추출된 의약품 코드: {med_codes}")
            
            # 감점 룰 조회
            scoring_rules = rule_service.get_cached_scoring_rules()
            logger.info(f"📋 로드된 감점 룰 수: {len(scoring_rules)}")
            
            for product in products:
                product_penalties = []
                total_penalty = 0.0
                
                # 제품 성분 태그 추출
                ingredient_tags = []
                if product.tags:
                    ingredient_tags = [tag.lower().strip() for tag in product.tags]
                
                # 각 룰에 대해 검사
                for rule in scoring_rules:
                    rule_applied = False
                    
                    # 의약품 코드 매칭
                    if rule.get('med_code') and rule['med_code'] in med_codes:
                        # 성분 태그 매칭
                        rule_ingredient = rule.get('ingredient_tag', '').lower().strip()
                        if rule_ingredient and rule_ingredient in ingredient_tags:
                            # 조건 검사
                            if self._check_rule_conditions(rule, request):
                                penalty = rule.get('weight', 10)
                                total_penalty += penalty
                                
                                product_penalties.append({
                                    'rule_id': rule.get('rule_id', 'unknown'),
                                    'penalty': penalty,
                                    'reason': rule.get('rationale_ko', '의약품 상호작용 주의'),
                                    'med_code': rule.get('med_code'),
                                    'ingredient': rule_ingredient
                                })
                                rule_applied = True
                
                if product_penalties:
                    penalties[product.product_id] = {
                        'total_penalty': total_penalty,
                        'rule_hits': product_penalties
                    }
            
            logger.info(f"🎯 감점 룰 적용 완료: {len(penalties)}개 제품에 감점 적용")
            logger.info(f"📊 총 감점 룰 수: {len(scoring_rules)}, 의약품 코드: {med_codes}")
            
            # 상세 로그
            for product_id, penalty_info in penalties.items():
                logger.info(f"🔍 제품 {product_id}: 총 감점 {penalty_info['total_penalty']}, 적용 룰 {len(penalty_info['rule_hits'])}개")
                for rule_hit in penalty_info['rule_hits']:
                    logger.info(f"  ⚠️  룰 {rule_hit['rule_id']}: {rule_hit['med_code']} + {rule_hit['ingredient']} = -{rule_hit['penalty']}점")
            
        except Exception as e:
            logger.error(f"의약품 감점 룰 적용 실패: {e}")
        finally:
            rule_service.close_session()
        
        return penalties
    
    def _check_rule_conditions(self, rule: Dict[str, Any], request) -> bool:
        """룰 조건 검사"""
        condition_json = rule.get('condition_json', {})
        if not condition_json:
            return True  # 조건이 없으면 항상 적용
        
        # 사용 맥락 검사
        if hasattr(request, 'use_context') and request.use_context:
            context = request.use_context
            
            # leave_on 조건
            if 'leave_on' in condition_json:
                if hasattr(context, 'leave_on') and context.leave_on != condition_json['leave_on']:
                    return False
            
            # day_use 조건
            if 'day_use' in condition_json:
                if hasattr(context, 'day_use') and context.day_use != condition_json['day_use']:
                    return False
            
            # face 조건
            if 'face' in condition_json:
                if hasattr(context, 'face') and context.face != condition_json['face']:
                    return False
        
        # 임신/수유 조건
        if 'preg_lact' in condition_json:
            if hasattr(request, 'med_profile') and request.med_profile:
                if hasattr(request.med_profile, 'preg_lact'):
                    if request.med_profile.preg_lact != condition_json['preg_lact']:
                        return False
        
        return True
    
    def _calculate_safety_penalty(self, product: Product, request) -> float:
        """안전성 기반 감점 계산"""
        penalty = 0.0
        penalty_details = []
        
        try:
            # 사용자 프로필 기반 안전성 검사
            if hasattr(request, 'user_profile') and request.user_profile:
                profile = request.user_profile
                
                # 알레르기 성분 검사
                if hasattr(profile, 'allergies') and profile.allergies:
                    product_tags = [tag.lower() for tag in (product.tags or [])]
                    product_name = product.name.lower()
                    
                    for allergy in profile.allergies:
                        allergy_lower = allergy.lower()
                        
                        # 제품 태그에서 알레르기 성분 검사
                        for tag in product_tags:
                            if allergy_lower in tag:
                                penalty += 20.0  # 알레르기 성분 발견 시 큰 감점
                                penalty_details.append(f"알레르기({allergy})=-20")
                                break
                        
                        # 제품명에서 알레르기 성분 검사
                        if allergy_lower in product_name:
                            penalty += 15.0
                            penalty_details.append(f"알레르기명({allergy})=-15")
                
                # 피부타입별 부적합 성분 검사
                if hasattr(profile, 'skin_type') and profile.skin_type:
                    skin_penalty = self._get_skin_type_penalty(product, profile.skin_type)
                    if skin_penalty > 0:
                        penalty += skin_penalty
                        penalty_details.append(f"피부타입({profile.skin_type})=-{skin_penalty}")
                
                # 연령대별 부적합 성분 검사
                if hasattr(profile, 'age_group') and profile.age_group:
                    age_penalty = self._get_age_safety_penalty(product, profile.age_group)
                    if age_penalty > 0:
                        penalty += age_penalty
                        penalty_details.append(f"연령({profile.age_group})=-{age_penalty}")
            
            # 제외 성분 검사
            if hasattr(request, 'exclude_ingredients') and request.exclude_ingredients:
                product_tags = [tag.lower() for tag in (product.tags or [])]
                product_name = product.name.lower()
                
                for exclude_ingredient in request.exclude_ingredients:
                    exclude_lower = exclude_ingredient.lower()
                    
                    for tag in product_tags:
                        if exclude_lower in tag:
                            penalty += 25.0  # 제외 성분 발견 시 큰 감점
                            penalty_details.append(f"제외성분({exclude_ingredient})=-25")
                            break
                    
                    if exclude_lower in product_name:
                        penalty += 20.0
                        penalty_details.append(f"제외성분명({exclude_ingredient})=-20")
        
        except Exception as e:
            logger.error(f"안전성 감점 계산 실패 (product_id: {product.product_id}): {e}")
        
        final_penalty = min(penalty, 50.0)  # 최대 50점 감점
        
        # 디버그 로그 (감점이 있는 경우만)
        if final_penalty > 0:
            logger.debug(f"⚠️  제품 {product.product_id} 안전성 감점: {'; '.join(penalty_details)} → -{final_penalty:.1f}")
        
        return final_penalty
    
    def _get_skin_type_penalty(self, product: Product, skin_type: str) -> float:
        """피부타입별 부적합 성분 감점"""
        penalty = 0.0
        product_tags = [tag.lower() for tag in (product.tags or [])]
        
        skin_avoid_keywords = {
            'sensitive': ['alcohol', '알코올', 'fragrance', '향료', 'aha', 'bha', '자극'],
            'dry': ['alcohol', '알코올', '수렴', 'astringent'],
            'oily': ['heavy', '무거운', 'comedogenic', '코메도제닉'],
            'combination': []  # 복합성은 특별한 제한 없음
        }
        
        avoid_keywords = skin_avoid_keywords.get(skin_type, [])
        
        for keyword in avoid_keywords:
            for tag in product_tags:
                if keyword in tag:
                    penalty += 5.0
                    break
        
        return penalty
    
    def _get_age_safety_penalty(self, product: Product, age_group: str) -> float:
        """연령대별 안전성 감점"""
        penalty = 0.0
        product_tags = [tag.lower() for tag in (product.tags or [])]
        
        age_avoid_keywords = {
            '10s': ['retinol', '레티놀', 'aha', 'bha', '강한성분'],
            '20s': ['고농도', 'high concentration'],
            '30s': [],
            '40s': [],
            '50s': ['자극', 'irritating']
        }
        
        avoid_keywords = age_avoid_keywords.get(age_group, [])
        
        for keyword in avoid_keywords:
            for tag in product_tags:
                if keyword in tag:
                    penalty += 8.0
                    break
        
        return penalty
    
    def _get_age_compatibility_score(self, product: Product, age_group: str) -> float:
        """연령대 적합성 점수 (개선된 버전)"""
        product_tags = [tag.lower() for tag in (product.tags or [])]
        product_name = product.name.lower()
        
        age_keywords = {
            '10s': {
                'positive': ['teen', '10대', '청소년', 'young', 'mild', '순한', '저자극'],
                'negative': ['레티놀', 'retinol', '안티에이징', 'anti-aging', '주름']
            },
            '20s': {
                'positive': ['20대', 'young', 'fresh', '청춘', '데일리', 'daily'],
                'negative': ['시니어', 'senior', '성숙']
            },
            '30s': {
                'positive': ['30대', 'anti-aging', '안티에이징', 'wrinkle', '주름', '탄력'],
                'negative': ['teen', '10대']
            },
            '40s': {
                'positive': ['40대', 'mature', '성숙', 'firming', '탄력', '집중케어'],
                'negative': ['teen', '10대', 'young']
            },
            '50s': {
                'positive': ['50대', 'mature', '시니어', 'intensive', '집중', '영양'],
                'negative': ['teen', '10대', 'young', 'fresh']
            }
        }
        
        age_config = age_keywords.get(age_group, {'positive': [], 'negative': []})
        score = 0.0
        
        # 긍정적 키워드 매칭
        for keyword in age_config['positive']:
            for tag in product_tags:
                if keyword in tag:
                    score += 8.0
                    break
            if keyword in product_name:
                score += 5.0
        
        # 부정적 키워드 페널티
        for keyword in age_config['negative']:
            for tag in product_tags:
                if keyword in tag:
                    score -= 5.0
                    break
            if keyword in product_name:
                score -= 3.0
        
        return max(-10.0, min(20.0, score))
    
    def _get_skin_type_compatibility_score(self, product: Product, skin_type: str) -> float:
        """피부타입 적합성 점수 (개선된 버전)"""
        product_tags = [tag.lower() for tag in (product.tags or [])]
        product_name = product.name.lower()
        
        skin_keywords = {
            'dry': {
                'positive': ['보습', '수분', 'moistur', 'hydrat', '건성', '수분보유', '수분공급', 'hyaluronic', '히알루론'],
                'negative': ['피지조절', '오일컨트롤', '수렴', '지성']
            },
            'oily': {
                'positive': ['피지', 'oil', '지성', 'sebum', '오일컨트롤', '피지조절', '수렴', '모공'],
                'negative': ['보습', '수분', '건성', '영양']
            },
            'combination': {
                'positive': ['복합성', 'combination', '밸런싱', '균형', '모공', '피지조절'],
                'negative': ['극건성', '극지성']
            },
            'sensitive': {
                'positive': ['민감', 'sensitive', '순한', 'gentle', '저자극', '진정', '수딩', '카밍'],
                'negative': ['자극', '강한', '필링', 'aha', 'bha', '레티놀']
            },
            'normal': {
                'positive': ['normal', '정상', 'balance', '밸런스', '데일리', 'daily'],
                'negative': []
            }
        }
        
        skin_config = skin_keywords.get(skin_type, {'positive': [], 'negative': []})
        score = 0.0
        
        # 긍정적 키워드 매칭
        positive_matches = 0
        for keyword in skin_config['positive']:
            for tag in product_tags:
                if keyword in tag:
                    score += 10.0
                    positive_matches += 1
                    break
            if keyword in product_name:
                score += 6.0
                positive_matches += 1
        
        # 부정적 키워드 페널티
        for keyword in skin_config['negative']:
            for tag in product_tags:
                if keyword in tag:
                    score -= 8.0
                    break
            if keyword in product_name:
                score -= 5.0
        
        # 다중 매칭 보너스
        if positive_matches >= 2:
            score += 5.0
        
        return max(-15.0, min(25.0, score))
    
    def _get_skin_concern_compatibility_score(self, product: Product, skin_concerns: List[str]) -> float:
        """피부 고민 적합성 점수"""
        product_tags = [tag.lower() for tag in (product.tags or [])]
        product_name = product.name.lower()
        
        concern_keywords = {
            'acne': ['여드름', 'acne', '트러블', 'blemish'],
            'wrinkles': ['주름', 'wrinkle', '안티에이징', 'anti-aging'],
            'dryness': ['건조', '보습', 'dry', 'moistur'],
            'sensitivity': ['민감', 'sensitive', '진정', 'soothing'],
            'pigmentation': ['미백', 'brightening', '색소', 'spot'],
            'pores': ['모공', 'pore', '블랙헤드', 'blackhead']
        }
        
        total_bonus = 0.0
        for concern in skin_concerns:
            keywords = concern_keywords.get(concern, [concern])
            for keyword in keywords:
                for tag in product_tags:
                    if keyword in tag:
                        total_bonus += 8.0
                        break
                if keyword in product_name:
                    total_bonus += 5.0
        
        return min(total_bonus, 20.0)
    
    def _calculate_safety_penalty(self, product: Product, request) -> float:
        """안전성 감점 계산"""
        penalty = 0.0
        
        # 알레르기 성분 체크
        if (hasattr(request, 'user_profile') and 
            request.user_profile and 
            hasattr(request.user_profile, 'allergies') and 
            request.user_profile.allergies):
            
            product_tags = [tag.lower() for tag in (product.tags or [])]
            product_name = product.name.lower()
            
            for allergy in request.user_profile.allergies:
                allergy_lower = allergy.lower()
                for tag in product_tags:
                    if allergy_lower in tag:
                        penalty += 30.0  # 알레르기 성분 발견 시 큰 감점
                        break
                if allergy_lower in product_name:
                    penalty += 20.0
        
        # 연령 제한 체크
        if (hasattr(request, 'user_profile') and 
            request.user_profile and 
            hasattr(request.user_profile, 'age_group')):
            
            age_group = request.user_profile.age_group
            product_name = product.name.lower()
            
            # 10대에게 부적합한 성분
            if age_group == '10s':
                risky_ingredients = ['레티놀', 'retinol', 'aha', 'bha', '필링']
                for ingredient in risky_ingredients:
                    if ingredient in product_name:
                        penalty += 15.0
        
        return min(penalty, 50.0)  # 최대 50점 감점
    
    def _apply_medication_scoring_rules(self, products: List[Product], request) -> Dict[int, Dict[str, Any]]:
        """의약품 기반 감점 룰 적용"""
        from app.services.rule_service import RuleService
        
        rule_service = RuleService()
        penalties = {}
        
        try:
            # 의약품 코드 추출
            med_codes = []
            if hasattr(request, 'med_profile') and request.med_profile and request.med_profile.codes:
                med_codes = request.med_profile.codes
            
            if not med_codes:
                return penalties  # 의약품 없으면 감점 없음
            
            # 의약품 코드 해석 (별칭 포함)
            resolved_codes = rule_service.resolve_med_codes_batch(med_codes)
            all_med_codes = set()
            for codes in resolved_codes.values():
                all_med_codes.update(codes)
            
            # 감점 룰 조회
            scoring_rules = rule_service.get_cached_scoring_rules()
            
            # 각 제품에 대해 감점 룰 적용
            for product in products:
                product_penalties = []
                total_penalty = 0
                
                product_tags = [tag.lower().strip() for tag in (product.tags or [])]
                
                for rule in scoring_rules:
                    # 의약품 코드 매칭
                    rule_med_code = rule.get('med_code')
                    if not rule_med_code or rule_med_code not in all_med_codes:
                        continue
                    
                    # 성분 태그 매칭
                    rule_ingredient = rule.get('ingredient_tag', '').lower().strip()
                    if not rule_ingredient:
                        continue
                    
                    # 태그 매칭 확인 (유연한 매칭)
                    tag_matched = False
                    for product_tag in product_tags:
                        if (rule_ingredient == product_tag or 
                            rule_ingredient in product_tag or 
                            product_tag in rule_ingredient):
                            tag_matched = True
                            break
                    
                    if tag_matched:
                        penalty_weight = rule.get('weight', 0)
                        total_penalty += penalty_weight
                        
                        rule_hit = {
                            'rule_id': rule.get('rule_id'),
                            'weight': penalty_weight,
                            'rationale_ko': rule.get('rationale_ko', ''),
                            'med_name_ko': rule.get('med_name_ko', ''),
                            'ingredient_tag': rule.get('ingredient_tag', '')
                        }
                        product_penalties.append(rule_hit)
                
                if total_penalty > 0:
                    penalties[product.product_id] = {
                        'total_penalty': min(total_penalty, 100),  # 최대 100점 감점
                        'rule_hits': product_penalties
                    }
            
            rule_service.close_session()
            return penalties
            
        except Exception as e:
            logger.error(f"의약품 감점 룰 적용 실패: {e}")
            rule_service.close_session()
            return penalties
    
    async def calculate_product_scores(
        self,
        products: List[Product],
        intent_tags: List[str],
        profile_matches: Dict[int, ProfileMatchResult],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]] = None,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> Dict[int, ProductScore]:
        """제품별 종합 점수 계산"""
        
        weights = custom_weights or self.default_weights
        results = {}
        
        # 병렬 처리를 위한 태스크 생성
        tasks = []
        for product in products:
            task = self._calculate_single_product_score(
                product, intent_tags, profile_matches, ingredient_analyses, 
                user_profile, weights
            )
            tasks.append(task)
        
        # 병렬 실행
        try:
            score_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(score_results):
                if isinstance(result, Exception):
                    logger.error(f"제품 점수 계산 실패 (product_id: {products[i].product_id}): {result}")
                    # 기본 점수로 폴백
                    results[products[i].product_id] = self._create_fallback_score(products[i])
                else:
                    results[products[i].product_id] = result
                    
        except Exception as e:
            logger.error(f"점수 계산 배치 처리 실패: {e}")
            raise ScoreCalculationError(f"점수 계산 실패: {e}")
        
        return results
    
    async def _calculate_single_product_score(
        self,
        product: Product,
        intent_tags: List[str],
        profile_matches: Dict[int, ProfileMatchResult],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> ProductScore:
        """개별 제품 점수 계산"""
        
        # 1. 의도 매칭 점수 계산
        intent_result = await self.intent_scorer.calculate_intent_score(product, intent_tags)
        intent_score = intent_result.intent_score
        
        # 2. 개인화 점수 (이미 계산됨)
        profile_match = profile_matches.get(product.product_id)
        personalization_score = profile_match.overall_match_score if profile_match else 50.0
        
        # 3. 안전성 점수 계산
        ingredient_analysis = ingredient_analyses.get(product.product_id)
        safety_result = await self.safety_scorer.calculate_safety_score(
            product, ingredient_analysis, user_profile
        )
        safety_score = safety_result.safety_score
        
        # 4. 최종 점수 계산 (가중 평균)
        total_weight = sum(weights.values())
        if total_weight == 0:
            final_score = 50.0
        else:
            final_score = (
                (intent_score * weights['intent']) +
                (personalization_score * weights['personalization']) +
                (safety_score * weights['safety'])
            ) / total_weight
        
        # 5. 점수 정규화
        normalized_score = max(0.0, min(100.0, final_score))
        
        # 6. 점수 상세 분석 생성
        score_breakdown = ScoreBreakdown(
            intent_score=intent_score,
            personalization_score=personalization_score,
            safety_score=safety_score,
            intent_weight=weights['intent'],
            personalization_weight=weights['personalization'],
            safety_weight=weights['safety']
        )
        
        # 7. 추천 근거 통합
        rationales = []
        if intent_result.match_rationales:
            rationales.extend([f"[의도] {r}" for r in intent_result.match_rationales[:2]])
        if profile_match and profile_match.match_reasons:
            rationales.extend([f"[개인화] {r}" for r in profile_match.match_reasons[:2]])
        
        # 8. 주의사항 통합
        cautions = []
        if safety_result.safety_warnings:
            cautions.extend(safety_result.safety_warnings[:2])
        if safety_result.age_restrictions:
            cautions.extend(safety_result.age_restrictions[:1])
        
        return ProductScore(
            product_id=product.product_id,
            product_name=product.name,
            brand_name=product.brand_name,
            final_score=final_score,
            normalized_score=normalized_score,
            score_breakdown=score_breakdown,
            ingredient_analysis=ingredient_analysis,
            profile_match=profile_match,
            recommendation_reasons=rationales[:5],
            caution_notes=cautions[:3]
        )
    
    def _create_fallback_score(self, product: Product) -> ProductScore:
        """폴백용 기본 점수 생성"""
        return ProductScore(
            product_id=product.product_id,
            product_name=product.name,
            brand_name=product.brand_name,
            final_score=50.0,
            normalized_score=50.0,
            score_breakdown=ScoreBreakdown(),
            recommendation_reasons=["기본 점수 적용"],
            caution_notes=["상세 분석 불가"]
        )
    
    def normalize_scores(self, scores: Dict[int, ProductScore]) -> Dict[int, ProductScore]:
        """점수 정규화 (0-100 범위)"""
        if not scores:
            return scores
        
        # 최고점과 최저점 찾기
        score_values = [score.final_score for score in scores.values()]
        min_score = min(score_values)
        max_score = max(score_values)
        
        # 정규화가 필요한 경우에만 적용
        if max_score - min_score > 0:
            for product_score in scores.values():
                # Min-Max 정규화
                normalized = ((product_score.final_score - min_score) / (max_score - min_score)) * 100
                product_score.normalized_score = normalized
        
        return scores
    
    def filter_outliers(self, scores: Dict[int, ProductScore], threshold: float = 2.0) -> Dict[int, ProductScore]:
        """이상치 필터링"""
        if len(scores) < 3:
            return scores
        
        score_values = [score.final_score for score in scores.values()]
        mean_score = sum(score_values) / len(score_values)
        
        # 표준편차 계산
        variance = sum((x - mean_score) ** 2 for x in score_values) / len(score_values)
        std_dev = variance ** 0.5
        
        # 이상치 제거
        filtered_scores = {}
        for product_id, score in scores.items():
            if abs(score.final_score - mean_score) <= threshold * std_dev:
                filtered_scores[product_id] = score
            else:
                logger.info(f"이상치 제거: product_id={product_id}, score={score.final_score}")
        
        return filtered_scores