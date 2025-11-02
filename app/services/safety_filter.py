"""
안전성 필터링 시스템
위험한 성분이나 사용자에게 부적합한 제품을 필터링하는 시스템
"""

from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

from app.models.personalization_models import (
    ProductScore, ProductIngredientAnalysis, SafetyLevel,
    PersonalizationEngineError
)
from app.models.postgres_models import Product

logger = logging.getLogger(__name__)

class FilterReason(Enum):
    """필터링 사유"""
    AGE_RESTRICTION = "age_restriction"      # 연령 제한
    SKIN_TYPE_RISK = "skin_type_risk"       # 피부타입 위험
    ALLERGY_RISK = "allergy_risk"           # 알레르기 위험
    HIGH_RISK_INGREDIENT = "high_risk"      # 고위험 성분
    EWG_GRADE_LIMIT = "ewg_grade_limit"     # EWG 등급 제한
    SAFETY_SCORE_LOW = "safety_score_low"   # 안전성 점수 미달

@dataclass
class FilterResult:
    """필터링 결과"""
    product_id: int
    is_filtered: bool
    filter_reasons: List[FilterReason] = field(default_factory=list)
    warning_messages: List[str] = field(default_factory=list)
    safety_notes: List[str] = field(default_factory=list)

@dataclass
class SafetyFilterConfig:
    """안전성 필터 설정"""
    # 연령별 설정
    age_group: Optional[str] = None
    min_safety_score: float = 40.0
    max_ewg_grade: float = 7.0
    
    # 피부타입별 설정
    skin_type: Optional[str] = None
    strict_filtering: bool = False
    
    # 전역 설정
    filter_high_risk: bool = True
    filter_allergens: bool = True
    allow_warnings: bool = True

class AgeBasedSafetyFilter:
    """연령별 안전성 필터"""
    
    def __init__(self):
        # 연령별 위험 성분 정의 (한국어 화장품 성분명 기준)
        self.age_risk_ingredients = {
            "10s": {
                "high_risk": [
                    "레티놀", "레티닐팔미테이트", "트레티노인",
                    "글리콜산", "살리실산", "젖산", "만델산",
                    "하이드로퀴논", "코직산", "아르부틴",
                    "벤조일퍼옥사이드", "과산화벤조일"
                ],
                "moderate_risk": [
                    "나이아신아마이드", "비타민C", "아스코르빅산",
                    "토코페롤", "판테놀"
                ],
                "min_safety_score": 60.0,
                "max_ewg_grade": 5.0
            },
            
            "20s": {
                "high_risk": [
                    "고농도레티놀", "트레티노인", "하이드로퀴논",
                    "강한필링성분", "TCA", "페놀필링"
                ],
                "moderate_risk": [
                    "레티놀", "글리콜산", "살리실산",
                    "벤조일퍼옥사이드"
                ],
                "min_safety_score": 50.0,
                "max_ewg_grade": 6.0
            },
            
            "30s": {
                "high_risk": [
                    "트레티노인", "하이드로퀴논", "TCA",
                    "강한자극성분", "메틸이소티아졸리논"
                ],
                "moderate_risk": [
                    "고농도레티놀", "강한필링성분",
                    "파라벤", "황산나트륨"
                ],
                "min_safety_score": 45.0,
                "max_ewg_grade": 7.0
            },
            
            "40s": {
                "high_risk": [
                    "알코올", "에탄올", "이소프로필알코올",
                    "강한방부제", "메틸이소티아졸리논",
                    "포름알데히드", "디아졸리디닐우레아"
                ],
                "moderate_risk": [
                    "파라벤", "황산나트륨", "라우릴황산나트륨",
                    "트리에탄올아민", "DEA", "TEA"
                ],
                "min_safety_score": 50.0,
                "max_ewg_grade": 6.0
            },
            
            "50s": {
                "high_risk": [
                    "자극성분", "알코올", "에탄올", "변성알코올",
                    "인공향료", "합성향료", "프탈레이트",
                    "강한계면활성제", "라우릴황산나트륨",
                    "메틸이소티아졸리논", "포름알데히드방출제"
                ],
                "moderate_risk": [
                    "파라벤", "페녹시에탄올", "벤질알코올",
                    "리모넨", "리날룰", "시트랄",
                    "황산나트륨", "코카미드DEA"
                ],
                "min_safety_score": 55.0,
                "max_ewg_grade": 5.0
            }
        }
        
        # 연령별 EWG 등급 허용 기준
        self.ewg_grade_limits = {
            "10s": 5.0,
            "20s": 6.0,
            "30s": 7.0,
            "40s": 6.0,
            "50s": 5.0
        }
    
    def filter_by_age(
        self, 
        products: List[Product], 
        product_scores: Dict[int, ProductScore],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        age_group: str
    ) -> Dict[int, FilterResult]:
        """연령별 안전성 필터링"""
        
        if age_group not in self.age_risk_ingredients:
            logger.warning(f"지원하지 않는 연령대: {age_group}")
            return {p.product_id: FilterResult(p.product_id, False) for p in products}
        
        age_config = self.age_risk_ingredients[age_group]
        results = {}
        
        for product in products:
            result = self._evaluate_product_for_age(
                product, product_scores.get(product.product_id),
                ingredient_analyses.get(product.product_id),
                age_group, age_config
            )
            results[product.product_id] = result
        
        return results
    
    def _evaluate_product_for_age(
        self,
        product: Product,
        product_score: Optional[ProductScore],
        ingredient_analysis: Optional[ProductIngredientAnalysis],
        age_group: str,
        age_config: Dict[str, Any]
    ) -> FilterResult:
        """개별 제품의 연령별 안전성 평가"""
        
        filter_reasons = []
        warnings = []
        safety_notes = []
        is_filtered = False
        
        # 1. 안전성 점수 기준 검사
        if product_score and product_score.score_breakdown.safety_score < age_config["min_safety_score"]:
            is_filtered = True
            filter_reasons.append(FilterReason.SAFETY_SCORE_LOW)
            warnings.append(f"{age_group}에 안전성 점수가 부족합니다 ({product_score.score_breakdown.safety_score:.1f})")
        
        # 2. EWG 등급 기준 검사
        if ingredient_analysis:
            high_ewg_ingredients = self._check_ewg_grades(
                ingredient_analysis, age_config["max_ewg_grade"]
            )
            if high_ewg_ingredients:
                is_filtered = True
                filter_reasons.append(FilterReason.EWG_GRADE_LIMIT)
                warnings.append(f"{age_group}에 부적합한 EWG 등급 성분: {', '.join(high_ewg_ingredients[:3])}")
        
        # 3. 위험 성분 검사
        high_risk_found = self._check_risk_ingredients(
            product, ingredient_analysis, age_config["high_risk"], "high"
        )
        if high_risk_found:
            is_filtered = True
            filter_reasons.append(FilterReason.AGE_RESTRICTION)
            warnings.append(f"{age_group}에 부적합한 고위험 성분: {', '.join(high_risk_found[:2])}")
        
        # 4. 중위험 성분 경고
        moderate_risk_found = self._check_risk_ingredients(
            product, ingredient_analysis, age_config["moderate_risk"], "moderate"
        )
        if moderate_risk_found:
            safety_notes.append(f"{age_group}에 주의 필요 성분: {', '.join(moderate_risk_found[:2])}")
        
        return FilterResult(
            product_id=product.product_id,
            is_filtered=is_filtered,
            filter_reasons=filter_reasons,
            warning_messages=warnings,
            safety_notes=safety_notes
        )
    
    def _check_ewg_grades(
        self, 
        ingredient_analysis: ProductIngredientAnalysis, 
        max_grade: float
    ) -> List[str]:
        """EWG 등급 기준 위반 성분 검사"""
        high_ewg_ingredients = []
        
        for effect in ingredient_analysis.beneficial_effects + ingredient_analysis.harmful_effects:
            # EWG 등급이 있는 경우 검사
            if hasattr(effect, 'ewg_grade') and effect.ewg_grade:
                try:
                    grade = float(effect.ewg_grade.replace('_', '.'))
                    if grade > max_grade:
                        high_ewg_ingredients.append(effect.ingredient_name)
                except (ValueError, AttributeError):
                    continue
        
        return high_ewg_ingredients
    
    def _check_risk_ingredients(
        self,
        product: Product,
        ingredient_analysis: Optional[ProductIngredientAnalysis],
        risk_ingredients: List[str],
        risk_level: str
    ) -> List[str]:
        """위험 성분 검사"""
        found_ingredients = []
        
        # 제품 태그에서 검사
        for tag in product.tags:
            tag_lower = tag.lower()
            for risk_ingredient in risk_ingredients:
                if risk_ingredient.lower() in tag_lower:
                    found_ingredients.append(risk_ingredient)
        
        # 성분 분석 결과에서 검사
        if ingredient_analysis:
            all_effects = (ingredient_analysis.beneficial_effects + 
                          ingredient_analysis.harmful_effects + 
                          ingredient_analysis.neutral_effects)
            
            for effect in all_effects:
                ingredient_name_lower = effect.ingredient_name.lower()
                for risk_ingredient in risk_ingredients:
                    if risk_ingredient.lower() in ingredient_name_lower:
                        found_ingredients.append(effect.ingredient_name)
        
        return list(set(found_ingredients))  # 중복 제거

class SkinTypeBasedSafetyFilter:
    """피부타입별 안전성 필터"""
    
    def __init__(self):
        # 피부타입별 위험 성분 정의
        self.skin_type_risks = {
            "sensitive": {
                "high_risk": [
                    "향료", "인공향료", "합성향료", "프래그런스",
                    "알코올", "에탄올", "변성알코올",
                    "자극성분", "멘톨", "캄파",
                    "라놀린", "프로필렌글리콜"
                ],
                "moderate_risk": [
                    "레티놀", "AHA", "BHA", "글리콜산",
                    "살리실산", "벤조일퍼옥사이드",
                    "비타민C", "나이아신아마이드"
                ],
                "allergens": [
                    "리모넨", "리날룰", "시트랄", "게라니올",
                    "시나말", "유제놀", "이소유제놀",
                    "벤질알코올", "벤질살리실레이트"
                ],
                "min_safety_score": 60.0
            },
            
            "dry": {
                "high_risk": [
                    "알코올", "에탄올", "이소프로필알코올",
                    "강한계면활성제", "라우릴황산나트륨",
                    "건조성분", "수렴제", "위치하젤"
                ],
                "moderate_risk": [
                    "BHA", "살리실산", "벤조일퍼옥사이드",
                    "클레이", "카올린", "벤토나이트"
                ],
                "min_safety_score": 50.0
            },
            
            "oily": {
                "high_risk": [
                    "과도한유분", "미네랄오일", "페트롤라툼",
                    "코메도제닉", "이소프로필미리스테이트",
                    "올레산", "코코넛오일"
                ],
                "moderate_risk": [
                    "시어버터", "아보카도오일", "올리브오일",
                    "라놀린", "스쿠알란"
                ],
                "comedogenic_ingredients": [
                    "이소프로필미리스테이트", "미리스틸미리스테이트",
                    "올레산", "이소프로필팔미테이트"
                ],
                "min_safety_score": 45.0
            },
            
            "combination": {
                "high_risk": [
                    "극단적성분", "과도한유분", "과도한건조성분"
                ],
                "moderate_risk": [
                    "강한보습제", "강한수렴제"
                ],
                "min_safety_score": 50.0
            }
        }
    
    def filter_by_skin_type(
        self,
        products: List[Product],
        product_scores: Dict[int, ProductScore],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        skin_type: str,
        strict_mode: bool = False
    ) -> Dict[int, FilterResult]:
        """피부타입별 안전성 필터링"""
        
        if skin_type not in self.skin_type_risks:
            logger.warning(f"지원하지 않는 피부타입: {skin_type}")
            return {p.product_id: FilterResult(p.product_id, False) for p in products}
        
        skin_config = self.skin_type_risks[skin_type]
        results = {}
        
        for product in products:
            result = self._evaluate_product_for_skin_type(
                product, product_scores.get(product.product_id),
                ingredient_analyses.get(product.product_id),
                skin_type, skin_config, strict_mode
            )
            results[product.product_id] = result
        
        return results
    
    def _evaluate_product_for_skin_type(
        self,
        product: Product,
        product_score: Optional[ProductScore],
        ingredient_analysis: Optional[ProductIngredientAnalysis],
        skin_type: str,
        skin_config: Dict[str, Any],
        strict_mode: bool
    ) -> FilterResult:
        """개별 제품의 피부타입별 안전성 평가"""
        
        filter_reasons = []
        warnings = []
        safety_notes = []
        is_filtered = False
        
        # 1. 안전성 점수 기준 검사
        if product_score and product_score.score_breakdown.safety_score < skin_config["min_safety_score"]:
            if strict_mode:
                is_filtered = True
                filter_reasons.append(FilterReason.SAFETY_SCORE_LOW)
            warnings.append(f"{skin_type} 피부에 안전성 점수가 낮습니다 ({product_score.score_breakdown.safety_score:.1f})")
        
        # 2. 고위험 성분 검사
        high_risk_found = self._check_skin_risk_ingredients(
            product, ingredient_analysis, skin_config["high_risk"]
        )
        if high_risk_found:
            is_filtered = True
            filter_reasons.append(FilterReason.SKIN_TYPE_RISK)
            warnings.append(f"{skin_type} 피부에 부적합: {', '.join(high_risk_found[:2])}")
        
        # 3. 중위험 성분 경고
        moderate_risk_found = self._check_skin_risk_ingredients(
            product, ingredient_analysis, skin_config["moderate_risk"]
        )
        if moderate_risk_found:
            if strict_mode:
                is_filtered = True
                filter_reasons.append(FilterReason.SKIN_TYPE_RISK)
                warnings.append(f"{skin_type} 피부에 주의 필요: {', '.join(moderate_risk_found[:2])}")
            else:
                safety_notes.append(f"{skin_type} 피부 주의 성분: {', '.join(moderate_risk_found[:2])}")
        
        # 4. 민감성 피부 알레르기 성분 검사
        if skin_type == "sensitive" and "allergens" in skin_config:
            allergen_found = self._check_skin_risk_ingredients(
                product, ingredient_analysis, skin_config["allergens"]
            )
            if allergen_found:
                is_filtered = True
                filter_reasons.append(FilterReason.ALLERGY_RISK)
                warnings.append(f"알레르기 위험 성분: {', '.join(allergen_found[:2])}")
        
        # 5. 지성 피부 코메도제닉 성분 검사
        if skin_type == "oily" and "comedogenic_ingredients" in skin_config:
            comedogenic_found = self._check_skin_risk_ingredients(
                product, ingredient_analysis, skin_config["comedogenic_ingredients"]
            )
            if comedogenic_found:
                if strict_mode:
                    is_filtered = True
                    filter_reasons.append(FilterReason.SKIN_TYPE_RISK)
                warnings.append(f"모공 막힘 위험: {', '.join(comedogenic_found[:2])}")
        
        return FilterResult(
            product_id=product.product_id,
            is_filtered=is_filtered,
            filter_reasons=filter_reasons,
            warning_messages=warnings,
            safety_notes=safety_notes
        )
    
    def _check_skin_risk_ingredients(
        self,
        product: Product,
        ingredient_analysis: Optional[ProductIngredientAnalysis],
        risk_ingredients: List[str]
    ) -> List[str]:
        """피부타입별 위험 성분 검사"""
        found_ingredients = []
        
        # 제품 태그에서 검사
        for tag in product.tags:
            tag_lower = tag.lower()
            for risk_ingredient in risk_ingredients:
                if risk_ingredient.lower() in tag_lower:
                    found_ingredients.append(risk_ingredient)
        
        # 성분 분석 결과에서 검사
        if ingredient_analysis:
            all_effects = (ingredient_analysis.beneficial_effects + 
                          ingredient_analysis.harmful_effects + 
                          ingredient_analysis.neutral_effects)
            
            for effect in all_effects:
                ingredient_name_lower = effect.ingredient_name.lower()
                for risk_ingredient in risk_ingredients:
                    if risk_ingredient.lower() in ingredient_name_lower:
                        found_ingredients.append(effect.ingredient_name)
        
        return list(set(found_ingredients))  # 중복 제거

class SafetyWarningSystem:
    """안전성 경고 시스템"""
    
    def __init__(self):
        # 경고 메시지 템플릿
        self.warning_templates = {
            FilterReason.AGE_RESTRICTION: {
                "title": "연령 제한",
                "template": "{age_group}에는 {ingredients} 성분이 부적합할 수 있습니다.",
                "severity": "warning"
            },
            FilterReason.SKIN_TYPE_RISK: {
                "title": "피부타입 주의",
                "template": "{skin_type} 피부에는 {ingredients} 성분을 주의해야 합니다.",
                "severity": "caution"
            },
            FilterReason.ALLERGY_RISK: {
                "title": "알레르기 위험",
                "template": "알레르기를 유발할 수 있는 {ingredients} 성분이 포함되어 있습니다.",
                "severity": "danger"
            },
            FilterReason.HIGH_RISK_INGREDIENT: {
                "title": "고위험 성분",
                "template": "고위험 성분 {ingredients}이 포함되어 있습니다.",
                "severity": "danger"
            },
            FilterReason.EWG_GRADE_LIMIT: {
                "title": "EWG 등급 주의",
                "template": "EWG 등급이 높은 {ingredients} 성분이 포함되어 있습니다.",
                "severity": "warning"
            },
            FilterReason.SAFETY_SCORE_LOW: {
                "title": "안전성 점수 미달",
                "template": "전체적인 안전성 점수가 기준에 미달합니다.",
                "severity": "caution"
            }
        }
        
        # 사용법 가이드
        self.usage_guides = {
            "sensitive": [
                "패치 테스트를 먼저 실시하세요",
                "소량부터 사용을 시작하세요",
                "자극이 느껴지면 즉시 사용을 중단하세요"
            ],
            "dry": [
                "충분한 보습제와 함께 사용하세요",
                "건조한 환경에서는 사용량을 줄이세요"
            ],
            "oily": [
                "모공이 막히지 않도록 주의하세요",
                "과도한 사용은 피지 분비를 증가시킬 수 있습니다"
            ]
        }
    
    def generate_warning_messages(
        self,
        filter_result: FilterResult,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """경고 메시지 생성"""
        warnings = []
        
        for reason in filter_result.filter_reasons:
            if reason in self.warning_templates:
                template_info = self.warning_templates[reason]
                
                # 메시지 생성
                message = self._format_warning_message(
                    template_info["template"], 
                    reason, 
                    filter_result.warning_messages,
                    user_profile
                )
                
                warnings.append({
                    "title": template_info["title"],
                    "message": message,
                    "severity": template_info["severity"]
                })
        
        return warnings
    
    def generate_usage_guide(
        self,
        filter_result: FilterResult,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """사용법 가이드 생성"""
        guides = []
        
        if user_profile:
            skin_type = user_profile.get('skin_type')
            if skin_type in self.usage_guides:
                guides.extend(self.usage_guides[skin_type])
        
        # 필터링 사유별 추가 가이드
        if FilterReason.ALLERGY_RISK in filter_result.filter_reasons:
            guides.append("알레르기 반응이 나타나면 즉시 사용을 중단하고 전문의와 상담하세요")
        
        if FilterReason.AGE_RESTRICTION in filter_result.filter_reasons:
            guides.append("연령에 적합한 제품 사용을 권장합니다")
        
        return guides
    
    def _format_warning_message(
        self,
        template: str,
        reason: FilterReason,
        warning_messages: List[str],
        user_profile: Optional[Dict[str, Any]]
    ) -> str:
        """경고 메시지 포맷팅"""
        
        # 기본 메시지에서 성분 추출
        ingredients = "해당 성분"
        if warning_messages:
            # 첫 번째 경고 메시지에서 성분명 추출 시도
            for msg in warning_messages:
                if ":" in msg:
                    ingredients = msg.split(":")[-1].strip()
                    break
        
        # 사용자 프로필 정보 추출
        format_params = {"ingredients": ingredients}
        if user_profile:
            format_params["age_group"] = user_profile.get('age_group', '해당 연령대')
            format_params["skin_type"] = user_profile.get('skin_type', '해당 피부타입')
        
        try:
            return template.format(**format_params)
        except KeyError:
            return template

class SafetyFilter:
    """통합 안전성 필터링 시스템"""
    
    def __init__(self):
        self.age_filter = AgeBasedSafetyFilter()
        self.skin_type_filter = SkinTypeBasedSafetyFilter()
        self.warning_system = SafetyWarningSystem()
    
    def filter_products(
        self,
        products: List[Product],
        product_scores: Dict[int, ProductScore],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]] = None,
        config: Optional[SafetyFilterConfig] = None
    ) -> Tuple[List[Product], Dict[int, FilterResult]]:
        """제품 안전성 필터링"""
        
        if not config:
            config = SafetyFilterConfig()
            if user_profile:
                config.age_group = user_profile.get('age_group')
                config.skin_type = user_profile.get('skin_type')
        
        all_filter_results = {}
        
        # 1. 연령별 필터링
        if config.age_group:
            age_results = self.age_filter.filter_by_age(
                products, product_scores, ingredient_analyses, config.age_group
            )
            all_filter_results.update(age_results)
        
        # 2. 피부타입별 필터링
        if config.skin_type:
            skin_results = self.skin_type_filter.filter_by_skin_type(
                products, product_scores, ingredient_analyses, 
                config.skin_type, config.strict_filtering
            )
            
            # 결과 병합
            for product_id, skin_result in skin_results.items():
                if product_id in all_filter_results:
                    # 기존 결과와 병합
                    existing = all_filter_results[product_id]
                    existing.is_filtered = existing.is_filtered or skin_result.is_filtered
                    existing.filter_reasons.extend(skin_result.filter_reasons)
                    existing.warning_messages.extend(skin_result.warning_messages)
                    existing.safety_notes.extend(skin_result.safety_notes)
                else:
                    all_filter_results[product_id] = skin_result
        
        # 3. 전역 안전성 필터링
        for product in products:
            if product.product_id not in all_filter_results:
                all_filter_results[product.product_id] = FilterResult(product.product_id, False)
            
            # 최소 안전성 점수 검사
            product_score = product_scores.get(product.product_id)
            if product_score and product_score.score_breakdown.safety_score < config.min_safety_score:
                result = all_filter_results[product.product_id]
                if config.filter_high_risk:
                    result.is_filtered = True
                    result.filter_reasons.append(FilterReason.SAFETY_SCORE_LOW)
                result.warning_messages.append(f"안전성 점수 미달: {product_score.score_breakdown.safety_score:.1f}")
        
        # 4. 필터링된 제품 제거
        filtered_products = [
            product for product in products 
            if not all_filter_results.get(product.product_id, FilterResult(product.product_id, False)).is_filtered
        ]
        
        # 5. 경고 메시지 생성
        for product_id, filter_result in all_filter_results.items():
            if filter_result.warning_messages or filter_result.safety_notes:
                warnings = self.warning_system.generate_warning_messages(filter_result, user_profile)
                guides = self.warning_system.generate_usage_guide(filter_result, user_profile)
                
                # ProductScore에 경고 정보 추가
                if product_id in product_scores:
                    product_score = product_scores[product_id]
                    product_score.caution_notes.extend([w["message"] for w in warnings])
                    product_score.caution_notes.extend(guides)
        
        logger.info(f"안전성 필터링 완료: {len(products)}개 → {len(filtered_products)}개")
        
        return filtered_products, all_filter_results