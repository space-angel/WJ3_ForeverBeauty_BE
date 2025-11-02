"""
성분 분석 엔진 구현
제품의 모든 성분을 분석하여 효능과 부작용을 평가하는 IngredientAnalyzer
"""

import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict
from datetime import datetime

from app.database.postgres_db import get_postgres_db
from app.models.postgres_models import Product, Ingredient, ProductWithIngredients
from app.models.personalization_models import (
    IngredientEffect, ProductIngredientAnalysis, EffectType, SafetyLevel,
    IngredientAnalysisError
)
from app.interfaces.personalization_interfaces import IIngredientAnalyzer
from app.services.ingredient_cache import get_product_analysis_cache

logger = logging.getLogger(__name__)

class IngredientAnalyzer(IIngredientAnalyzer):
    """성분 분석 엔진 - PostgreSQL 최적화"""
    
    def __init__(self):
        self.db = get_postgres_db()
        self.cache = get_product_analysis_cache()  # 고도화된 캐싱 시스템
        
    async def analyze_product_ingredients(
        self, 
        product: Product, 
        ingredients: List[Ingredient],
        user_profile: Optional[Any] = None
    ) -> ProductIngredientAnalysis:
        """
        제품의 성분을 분석하여 효능과 부작용을 평가
        
        Args:
            product: 분석할 제품
            ingredients: 제품에 포함된 성분 목록 (ordinal 순서대로 정렬됨)
            user_profile: 사용자 프로필 (개인화 분석용)
            
        Returns:
            ProductIngredientAnalysis: 성분 분석 결과
        """
        try:
            # 제품 성분 분석 시작
            
            # 캐시 확인
            if cached_result := self.cache.get_product_analysis(product.product_id):
                logger.debug(f"캐시에서 분석 결과 반환: {product.product_id}")
                return cached_result
            
            # 성분 효과 분석
            beneficial_effects = []
            harmful_effects = []
            neutral_effects = []
            safety_warnings = []
            allergy_risks = []
            age_restrictions = []
            
            analyzed_count = 0
            
            for idx, ingredient in enumerate(ingredients):
                try:
                    # 개별 성분 분석
                    effect = await self.analyze_single_ingredient(ingredient, user_profile)
                    
                    # 농도 순위 적용 (ordinal 기반)
                    effect.concentration_rank = idx + 1
                    
                    # 농도 기반 가중치 계산 및 적용
                    concentration_weight = await self.calculate_concentration_weight(idx + 1, len(ingredients))
                    
                    # 가중치를 신뢰도 점수에 반영
                    original_confidence = effect.confidence_score
                    effect.confidence_score = min(1.0, original_confidence * concentration_weight)
                    
                    logger.debug(f"성분 {ingredient.korean} - 순위: {idx+1}, 가중치: {concentration_weight:.2f}, "
                               f"신뢰도: {original_confidence:.2f} -> {effect.confidence_score:.2f}")
                    
                    # 효과 타입별 분류
                    if effect.effect_type == EffectType.BENEFICIAL:
                        beneficial_effects.append(effect)
                    elif effect.effect_type == EffectType.HARMFUL:
                        harmful_effects.append(effect)
                    else:
                        neutral_effects.append(effect)
                    
                    # 안전성 정보 수집 (상위 5개 성분의 부작용은 더 중요하게 처리)
                    if effect.safety_level in [SafetyLevel.WARNING, SafetyLevel.DANGER]:
                        warning_msg = f"{ingredient.korean}: {effect.effect_description}"
                        if idx < 5:  # 상위 5개 성분
                            warning_msg = f"⚠️ 주요성분 {warning_msg}"
                        safety_warnings.append(warning_msg)
                    
                    if ingredient.is_allergy:
                        allergy_msg = ingredient.korean
                        if idx < 5:
                            allergy_msg = f"⚠️ 주요성분 {allergy_msg}"
                        allergy_risks.append(allergy_msg)
                    
                    if ingredient.is_twenty:  # 20세 미만 사용 금지
                        age_msg = f"{ingredient.korean}: 20세 미만 사용 금지"
                        if idx < 5:
                            age_msg = f"⚠️ 주요성분 {age_msg}"
                        age_restrictions.append(age_msg)
                    
                    analyzed_count += 1
                    
                except Exception as e:
                    logger.warning(f"성분 분석 실패 - {ingredient.korean}: {e}")
                    continue
            
            # 분석 결과 생성
            analysis = ProductIngredientAnalysis(
                product_id=product.product_id,
                product_name=product.name,
                total_ingredients=len(ingredients),
                analyzed_ingredients=analyzed_count,
                beneficial_effects=beneficial_effects,
                harmful_effects=harmful_effects,
                neutral_effects=neutral_effects,
                safety_warnings=safety_warnings,
                allergy_risks=allergy_risks,
                age_restrictions=age_restrictions,
                analysis_timestamp=datetime.now(),
                analysis_version="1.0"
            )
            
            # 캐시 저장
            self.cache.set_product_analysis(product.product_id, analysis)
            
            # 성분 분석 완료
            return analysis
            
        except Exception as e:
            logger.error(f"제품 성분 분석 오류: {e}")
            raise IngredientAnalysisError(f"제품 {product.product_id} 성분 분석 실패: {e}")
    
    async def analyze_single_ingredient(
        self,
        ingredient: Ingredient,
        user_profile: Optional[Any] = None
    ) -> IngredientEffect:
        """
        개별 성분 분석
        
        Args:
            ingredient: 분석할 성분
            user_profile: 사용자 프로필
            
        Returns:
            IngredientEffect: 성분 효과 분석 결과
        """
        try:
            # 개별 성분 캐시 확인 (사용자 프로필 독립적인 기본 분석)
            if user_profile is None:
                if cached_effect := self.cache.get_ingredient_effect(ingredient.ingredient_id):
                    logger.debug(f"캐시에서 성분 효과 반환: {ingredient.korean}")
                    return cached_effect
            # 유익한 효과 분석
            beneficial_effects = self._parse_effects(ingredient.skin_good) if ingredient.skin_good else []
            
            # 부작용 분석
            harmful_effects = self._parse_effects(ingredient.skin_bad) if ingredient.skin_bad else []
            
            # 주요 효과 결정 (유익한 효과가 있으면 BENEFICIAL, 부작용만 있으면 HARMFUL)
            if beneficial_effects and not harmful_effects:
                effect_type = EffectType.BENEFICIAL
                effect_description = ", ".join(beneficial_effects[:3])  # 상위 3개 효과
            elif harmful_effects and not beneficial_effects:
                effect_type = EffectType.HARMFUL
                effect_description = ", ".join(harmful_effects[:3])
            elif beneficial_effects and harmful_effects:
                # 둘 다 있으면 유익한 효과를 우선하되 주의사항 포함
                effect_type = EffectType.BENEFICIAL
                effect_description = f"{', '.join(beneficial_effects[:2])} (주의: {harmful_effects[0]})"
            else:
                effect_type = EffectType.NEUTRAL
                effect_description = "효과 정보 없음"
            
            # 안전성 수준 결정
            safety_level = self._determine_safety_level(ingredient, harmful_effects)
            
            # 신뢰도 점수 계산
            confidence_score = self._calculate_confidence_score(ingredient)
            
            # 피부타입별 적합도 계산
            skin_type_suitability = self._calculate_skin_type_suitability(ingredient)
            
            effect = IngredientEffect(
                ingredient_id=ingredient.ingredient_id,
                ingredient_name=ingredient.korean,
                effect_type=effect_type,
                effect_description=effect_description,
                confidence_score=confidence_score,
                safety_level=safety_level,
                ewg_grade=ingredient.ewg_grade,
                is_allergy_risk=ingredient.is_allergy,
                is_age_restricted=ingredient.is_twenty,
                skin_type_suitability=skin_type_suitability
            )
            
            # 사용자 프로필 독립적인 경우 캐시 저장
            if user_profile is None:
                self.cache.set_ingredient_effect(ingredient.ingredient_id, effect, ttl=7200)  # 2시간
            
            return effect
            
        except Exception as e:
            logger.error(f"성분 분석 오류 - {ingredient.korean}: {e}")
            # 기본 중성 효과 반환
            return IngredientEffect(
                ingredient_id=ingredient.ingredient_id,
                ingredient_name=ingredient.korean,
                effect_type=EffectType.NEUTRAL,
                effect_description="분석 실패",
                confidence_score=0.0,
                safety_level=SafetyLevel.SAFE
            )
    
    async def get_ingredient_interactions(
        self,
        ingredients: List[Ingredient]
    ) -> List[Dict[str, Any]]:
        """
        성분 간 상호작용 분석 (기본 구현)
        
        Args:
            ingredients: 분석할 성분 목록
            
        Returns:
            List[Dict]: 상호작용 정보 목록
        """
        interactions = []
        
        # 기본적인 상호작용 패턴 확인
        ingredient_names = [ing.korean for ing in ingredients]
        
        # 산성 성분과 레티놀 조합 확인
        acids = ['살리실산', '글리콜산', '젖산', 'AHA', 'BHA']
        retinoids = ['레티놀', '레티닐팔미테이트', '레티날데하이드']
        
        has_acid = any(acid in name for name in ingredient_names for acid in acids)
        has_retinoid = any(retinoid in name for name in ingredient_names for retinoid in retinoids)
        
        if has_acid and has_retinoid:
            interactions.append({
                'type': 'caution',
                'description': '산성 성분과 레티놀 성분의 동시 사용 시 자극 가능성',
                'recommendation': '저녁에 번갈아 사용 권장'
            })
        
        return interactions
    
    async def get_product_ingredients_batch(self, product_ids: List[int]) -> Dict[int, List[Ingredient]]:
        """
        여러 제품의 성분을 배치로 조회 (N+1 문제 방지)
        
        Args:
            product_ids: 제품 ID 목록
            
        Returns:
            Dict[int, List[Ingredient]]: 제품 ID별 성분 목록
        """
        try:
            query = """
            SELECT 
                pi.product_id,
                i.ingredient_id, i.korean, i.english, i.ewg_grade,
                i.is_allergy, i.is_twenty, i.skin_type_code,
                i.skin_good, i.skin_bad, i.limitation, i.forbidden,
                i.purposes, i.tags, pi.ordinal
            FROM product_ingredients pi
            JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
            WHERE pi.product_id = ANY($1)
            ORDER BY pi.product_id, pi.ordinal
            """
            
            results = await self.db.execute_query(query, product_ids)
            
            # 제품별로 그룹핑
            grouped = defaultdict(list)
            for row in results:
                ingredient = Ingredient.from_db_row(row)
                grouped[row['product_id']].append(ingredient)
            
            # 배치 성분 조회 완료
            return dict(grouped)
            
        except Exception as e:
            logger.error(f"배치 성분 조회 오류: {e}")
            raise IngredientAnalysisError(f"배치 성분 조회 실패: {e}")
    
    def _parse_effects(self, effects_text: str) -> List[str]:
        """
        효과 텍스트를 파싱하여 개별 효과 추출
        
        Args:
            effects_text: 효과 설명 텍스트
            
        Returns:
            List[str]: 파싱된 효과 목록
        """
        if not effects_text:
            return []
        
        # 다양한 구분자로 분리
        separators = [',', ';', '\n', '/', '·', '•', '|', '&']
        for sep in separators:
            effects_text = effects_text.replace(sep, '||')
        
        effects = []
        for effect in effects_text.split('||'):
            effect = effect.strip()
            if effect and len(effect) > 1:  # 의미있는 효과만 포함
                # 효과 정규화 및 분류
                normalized_effect = self._normalize_effect(effect)
                if normalized_effect:
                    effects.append(normalized_effect)
        
        return effects[:10]  # 최대 10개까지만
    
    def _normalize_effect(self, effect: str) -> Optional[str]:
        """
        효과 텍스트 정규화 및 표준화
        
        Args:
            effect: 원본 효과 텍스트
            
        Returns:
            Optional[str]: 정규화된 효과 (무효한 경우 None)
        """
        effect = effect.strip().lower()
        
        # 무의미한 텍스트 필터링
        invalid_patterns = ['등', '기타', '다양한', '여러', '각종', '일반적인']
        if any(pattern in effect for pattern in invalid_patterns):
            return None
        
        # 효과 카테고리별 표준화
        effect_mapping = {
            # 보습 관련
            '보습': ['보습', '수분공급', '수분보충', '촉촉', '건조방지'],
            '수분증발방지': ['수분증발방지', '수분손실방지', '보습막형성'],
            
            # 피지/모공 관련
            '피지조절': ['피지조절', '유분조절', '피지분비억제', '기름기제거'],
            '수렴': ['수렴', '모공수축', '모공케어', '모공축소'],
            
            # 진정/항염 관련
            '진정': ['진정', '자극완화', '염증완화', '쿨링'],
            '항염': ['항염', '염증억제', '항염작용'],
            
            # 안티에이징 관련
            '주름개선': ['주름개선', '주름완화', '탄력증진', '리프팅'],
            '미백': ['미백', '브라이트닝', '톤업', '화이트닝'],
            
            # 각질/필링 관련
            '각질제거': ['각질제거', '필링', '엑스폴리에이션', '스크럽'],
            '세포재생': ['세포재생', '턴오버촉진', '재생촉진'],
            
            # 보호 관련
            'UV차단': ['자외선차단', 'UV차단', '선블록', '자외선보호'],
            '항산화': ['항산화', '산화방지', '프리라디칼제거']
        }
        
        # 매핑된 표준 효과 찾기
        for standard_effect, variations in effect_mapping.items():
            if any(var in effect for var in variations):
                return standard_effect
        
        # 매핑되지 않은 경우 원본 반환 (길이 제한)
        if len(effect) <= 20:
            return effect
        
        return None
    
    def _analyze_ingredient_purposes(self, ingredient: Ingredient) -> List[str]:
        """
        성분의 purposes JSON 데이터 분석
        
        Args:
            ingredient: 성분 정보
            
        Returns:
            List[str]: 분석된 목적 목록
        """
        purposes = []
        
        if not ingredient.purposes:
            return purposes
        
        try:
            # purposes가 이미 리스트인 경우와 JSON 문자열인 경우 모두 처리
            if isinstance(ingredient.purposes, list):
                purpose_data = ingredient.purposes
            else:
                purpose_data = json.loads(ingredient.purposes)
            
            for purpose_item in purpose_data:
                if isinstance(purpose_item, dict):
                    # 딕셔너리 형태의 purpose 처리
                    if 'name' in purpose_item:
                        purposes.append(purpose_item['name'])
                    elif 'purpose' in purpose_item:
                        purposes.append(purpose_item['purpose'])
                elif isinstance(purpose_item, str):
                    # 문자열 형태의 purpose 처리
                    purposes.append(purpose_item)
                    
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"purposes 파싱 오류 - {ingredient.korean}: {e}")
        
        return purposes[:5]  # 최대 5개까지
    
    def _calculate_ewg_safety_score(self, ewg_grade: Optional[str]) -> float:
        """
        EWG 등급 기반 안전성 점수 계산
        
        Args:
            ewg_grade: EWG 등급
            
        Returns:
            float: 안전성 점수 (0-100)
        """
        if not ewg_grade or ewg_grade == 'unknown':
            return 50.0  # 기본 점수
        
        try:
            # EWG 등급을 숫자로 변환 (1_2 -> 1.5)
            grade_value = float(ewg_grade.replace('_', '.'))
            
            # 1-10 등급을 100-0 점수로 변환
            # 1등급 = 100점, 10등급 = 0점
            safety_score = max(0, 100 - (grade_value - 1) * 11.11)
            
            return round(safety_score, 1)
            
        except ValueError:
            logger.warning(f"EWG 등급 파싱 오류: {ewg_grade}")
            return 50.0
    
    def _determine_safety_level(self, ingredient: Ingredient, harmful_effects: List[str]) -> SafetyLevel:
        """
        성분의 안전성 수준 결정
        
        Args:
            ingredient: 성분 정보
            harmful_effects: 부작용 목록
            
        Returns:
            SafetyLevel: 안전성 수준
        """
        # EWG 등급 기반 안전성 평가
        if ingredient.ewg_grade:
            try:
                grade = float(ingredient.ewg_grade.replace('_', '.'))
                if grade >= 7:
                    return SafetyLevel.DANGER
                elif grade >= 4:
                    return SafetyLevel.WARNING
                elif grade >= 3:
                    return SafetyLevel.CAUTION
            except ValueError:
                pass
        
        # 알레르기 위험성
        if ingredient.is_allergy:
            return SafetyLevel.WARNING
        
        # 연령 제한
        if ingredient.is_twenty:
            return SafetyLevel.CAUTION
        
        # 부작용 개수 기반
        if len(harmful_effects) >= 3:
            return SafetyLevel.WARNING
        elif len(harmful_effects) >= 1:
            return SafetyLevel.CAUTION
        
        return SafetyLevel.SAFE
    
    def _calculate_confidence_score(self, ingredient: Ingredient) -> float:
        """
        성분 분석 신뢰도 점수 계산
        
        Args:
            ingredient: 성분 정보
            
        Returns:
            float: 신뢰도 점수 (0.0-1.0)
        """
        score = 0.5  # 기본 점수
        
        # 효과 정보 존재 여부
        if ingredient.skin_good:
            score += 0.2
        if ingredient.skin_bad:
            score += 0.1
        
        # EWG 등급 존재 여부
        if ingredient.ewg_grade and ingredient.ewg_grade != 'unknown':
            score += 0.2
        
        # purposes 정보 존재 여부
        if ingredient.purposes:
            score += 0.1
        
        return min(1.0, score)
    
    async def analyze_ingredient_concentration_impact(
        self, 
        ingredients: List[Ingredient], 
        target_ingredient_id: int
    ) -> float:
        """
        성분 농도가 효능에 미치는 영향 분석
        
        Args:
            ingredients: 제품의 전체 성분 목록 (ordinal 순서)
            target_ingredient_id: 분석 대상 성분 ID
            
        Returns:
            float: 농도 영향 가중치 (0.1-2.0)
        """
        # 성분의 순서(ordinal) 찾기
        for idx, ingredient in enumerate(ingredients):
            if ingredient.ingredient_id == target_ingredient_id:
                position = idx + 1
                total_ingredients = len(ingredients)
                
                # 상위 5개 성분은 높은 가중치
                if position <= 5:
                    return 2.0 - (position - 1) * 0.3  # 2.0, 1.7, 1.4, 1.1, 0.8
                # 상위 10개 성분은 중간 가중치
                elif position <= 10:
                    return 0.8 - (position - 6) * 0.1  # 0.7, 0.6, 0.5, 0.4, 0.3
                # 나머지는 낮은 가중치
                else:
                    return max(0.1, 0.3 - (position - 11) * 0.02)
        
        return 0.5  # 기본값
    
    async def get_ingredient_synergy_effects(
        self, 
        ingredients: List[Ingredient]
    ) -> List[Dict[str, Any]]:
        """
        성분 간 시너지 효과 분석
        
        Args:
            ingredients: 분석할 성분 목록
            
        Returns:
            List[Dict]: 시너지 효과 정보
        """
        synergies = []
        ingredient_names = [ing.korean.lower() for ing in ingredients]
        
        # 알려진 시너지 조합들
        synergy_combinations = {
            ('비타민c', '비타민e'): {
                'effect': '항산화 시너지',
                'description': '비타민C와 비타민E의 상호보완적 항산화 효과',
                'boost_factor': 1.3
            },
            ('나이아신아마이드', '히알루론산'): {
                'effect': '보습 + 피지조절',
                'description': '나이아신아마이드의 피지조절과 히알루론산의 보습 효과',
                'boost_factor': 1.2
            },
            ('세라마이드', '콜레스테롤'): {
                'effect': '피부장벽 강화',
                'description': '세라마이드와 콜레스테롤의 피부장벽 복원 시너지',
                'boost_factor': 1.4
            },
            ('펩타이드', '레티놀'): {
                'effect': '안티에이징 강화',
                'description': '펩타이드와 레티놀의 주름개선 시너지',
                'boost_factor': 1.3
            }
        }
        
        # 시너지 조합 확인
        for (ingredient1, ingredient2), synergy_info in synergy_combinations.items():
            has_ingredient1 = any(ingredient1 in name for name in ingredient_names)
            has_ingredient2 = any(ingredient2 in name for name in ingredient_names)
            
            if has_ingredient1 and has_ingredient2:
                synergies.append({
                    'ingredients': [ingredient1, ingredient2],
                    'synergy_type': synergy_info['effect'],
                    'description': synergy_info['description'],
                    'boost_factor': synergy_info['boost_factor']
                })
        
        return synergies
    
    async def analyze_seasonal_suitability(
        self, 
        ingredient: Ingredient
    ) -> Dict[str, float]:
        """
        성분의 계절별 적합도 분석
        
        Args:
            ingredient: 분석할 성분
            
        Returns:
            Dict[str, float]: 계절별 적합도 (spring, summer, autumn, winter)
        """
        suitability = {
            'spring': 0.5,
            'summer': 0.5,
            'autumn': 0.5,
            'winter': 0.5
        }
        
        ingredient_name = ingredient.korean.lower()
        
        # 계절별 성분 특성
        seasonal_preferences = {
            'summer': {
                'preferred': ['히알루론산', '나이아신아마이드', '살리실산', '자외선차단제'],
                'avoided': ['오일', '바셀린', '시어버터']
            },
            'winter': {
                'preferred': ['세라마이드', '스쿠알란', '시어버터', '오일'],
                'avoided': ['알코올', '멘톨']
            },
            'spring': {
                'preferred': ['비타민c', '알파하이드록시산', '진정성분'],
                'avoided': ['강한필링성분']
            },
            'autumn': {
                'preferred': ['레티놀', '펩타이드', '보습성분'],
                'avoided': ['강한자극성분']
            }
        }
        
        for season, preferences in seasonal_preferences.items():
            # 선호 성분 확인
            for preferred in preferences['preferred']:
                if preferred in ingredient_name:
                    suitability[season] += 0.3
            
            # 기피 성분 확인
            for avoided in preferences['avoided']:
                if avoided in ingredient_name:
                    suitability[season] -= 0.3
        
        # 0.0-1.0 범위로 제한
        for season in suitability:
            suitability[season] = max(0.0, min(1.0, suitability[season]))
        
        return suitability
    
    async def calculate_concentration_weight(self, position: int, total_ingredients: int) -> float:
        """
        성분 순서(ordinal)를 기반으로 농도 가중치 계산
        
        Args:
            position: 성분 순서 (1부터 시작)
            total_ingredients: 전체 성분 개수
            
        Returns:
            float: 농도 가중치 (0.1-2.0)
        """
        # 상위 5개 성분은 높은 가중치 (주요 성분)
        if position <= 5:
            weights = [2.0, 1.8, 1.6, 1.4, 1.2]
            return weights[position - 1]
        
        # 6-10위는 중간 가중치
        elif position <= 10:
            return 1.0 - (position - 6) * 0.15  # 0.85, 0.7, 0.55, 0.4, 0.25
        
        # 11-20위는 낮은 가중치
        elif position <= 20:
            return 0.25 - (position - 11) * 0.015  # 0.235 ~ 0.1
        
        # 21위 이후는 최소 가중치
        else:
            return max(0.05, 0.1 - (position - 21) * 0.005)
    
    async def analyze_key_ingredients_impact(
        self, 
        ingredients: List[Ingredient]
    ) -> Dict[str, Any]:
        """
        상위 5개 주요 성분의 영향도 분석
        
        Args:
            ingredients: 성분 목록 (ordinal 순서)
            
        Returns:
            Dict: 주요 성분 영향도 분석 결과
        """
        key_ingredients = ingredients[:5]  # 상위 5개
        
        analysis = {
            'key_ingredient_count': len(key_ingredients),
            'beneficial_key_ingredients': [],
            'harmful_key_ingredients': [],
            'key_ingredient_effects': {},
            'concentration_impact_score': 0.0
        }
        
        total_impact = 0.0
        
        for idx, ingredient in enumerate(key_ingredients):
            position = idx + 1
            weight = await self.calculate_concentration_weight(position, len(ingredients))
            
            # 성분 효과 분석
            beneficial_effects = self._parse_effects(ingredient.skin_good) if ingredient.skin_good else []
            harmful_effects = self._parse_effects(ingredient.skin_bad) if ingredient.skin_bad else []
            
            ingredient_impact = {
                'name': ingredient.korean,
                'position': position,
                'concentration_weight': weight,
                'beneficial_effects': beneficial_effects,
                'harmful_effects': harmful_effects,
                'ewg_grade': ingredient.ewg_grade,
                'safety_score': self._calculate_ewg_safety_score(ingredient.ewg_grade)
            }
            
            # 유익/유해 성분 분류
            if beneficial_effects and not harmful_effects:
                analysis['beneficial_key_ingredients'].append(ingredient_impact)
                total_impact += weight * 1.0  # 긍정적 영향
            elif harmful_effects and not beneficial_effects:
                analysis['harmful_key_ingredients'].append(ingredient_impact)
                total_impact += weight * -0.5  # 부정적 영향 (가중치 감소)
            elif beneficial_effects and harmful_effects:
                # 혼합 효과는 유익한 쪽으로 분류하되 가중치 감소
                analysis['beneficial_key_ingredients'].append(ingredient_impact)
                total_impact += weight * 0.7
            
            analysis['key_ingredient_effects'][ingredient.korean] = ingredient_impact
        
        # 전체 농도 영향 점수 계산 (0-100)
        max_possible_impact = sum(await self.calculate_concentration_weight(i+1, len(ingredients)) 
                                for i in range(5))
        analysis['concentration_impact_score'] = max(0, min(100, 
            50 + (total_impact / max_possible_impact) * 50))
        
        return analysis
    
    async def get_concentration_based_recommendations(
        self, 
        ingredients: List[Ingredient]
    ) -> List[str]:
        """
        농도 기반 사용 권장사항 생성
        
        Args:
            ingredients: 성분 목록
            
        Returns:
            List[str]: 권장사항 목록
        """
        recommendations = []
        key_ingredients = ingredients[:5]
        
        # 상위 성분 중 주의사항 확인
        high_concentration_concerns = []
        
        for idx, ingredient in enumerate(key_ingredients):
            position = idx + 1
            
            # 자극성 성분이 상위에 있는 경우
            if ingredient.skin_bad and any(keyword in ingredient.skin_bad.lower() 
                                         for keyword in ['자극', '알레르기', '민감']):
                high_concentration_concerns.append(
                    f"{position}번째 주요성분 '{ingredient.korean}'은 자극 가능성이 있어 패치테스트 권장"
                )
            
            # EWG 등급이 높은 성분이 상위에 있는 경우
            if ingredient.ewg_grade:
                try:
                    grade = float(ingredient.ewg_grade.replace('_', '.'))
                    if grade >= 4 and position <= 3:
                        high_concentration_concerns.append(
                            f"{position}번째 주요성분 '{ingredient.korean}'은 EWG 등급 {ingredient.ewg_grade}로 주의 필요"
                        )
                except ValueError:
                    pass
            
            # 연령 제한 성분이 상위에 있는 경우
            if ingredient.is_twenty and position <= 3:
                high_concentration_concerns.append(
                    f"{position}번째 주요성분 '{ingredient.korean}'은 20세 미만 사용 금지"
                )
        
        recommendations.extend(high_concentration_concerns)
        
        # 일반적인 농도 기반 권장사항
        if len(key_ingredients) >= 3:
            active_ingredients = []
            for ingredient in key_ingredients:
                if ingredient.skin_good and any(keyword in ingredient.skin_good.lower() 
                                              for keyword in ['개선', '치료', '효과']):
                    active_ingredients.append(ingredient.korean)
            
            if len(active_ingredients) >= 2:
                recommendations.append(
                    f"활성성분 {len(active_ingredients)}개가 주요성분으로 포함되어 있어 점진적 사용 권장"
                )
        
        return recommendations
    
    def _calculate_skin_type_suitability(self, ingredient: Ingredient) -> Dict[str, float]:
        """
        피부타입별 성분 적합도 계산
        
        Args:
            ingredient: 성분 정보
            
        Returns:
            Dict[str, float]: 피부타입별 적합도 (0.0-1.0)
        """
        suitability = {
            'dry': 0.5,
            'oily': 0.5,
            'sensitive': 0.5,
            'combination': 0.5
        }
        
        # skin_good 기반 적합도 조정
        if ingredient.skin_good:
            good_effects = ingredient.skin_good.lower()
            
            # 건성 피부 적합 성분
            if any(keyword in good_effects for keyword in ['보습', '수분', '건조', '유연']):
                suitability['dry'] += 0.3
            
            # 지성 피부 적합 성분
            if any(keyword in good_effects for keyword in ['피지', '수렴', '모공', '유분']):
                suitability['oily'] += 0.3
            
            # 민감성 피부 적합 성분
            if any(keyword in good_effects for keyword in ['진정', '항염', '자극완화', '순한']):
                suitability['sensitive'] += 0.3
        
        # skin_bad 기반 적합도 조정
        if ingredient.skin_bad:
            bad_effects = ingredient.skin_bad.lower()
            
            # 민감성 피부 부적합 성분
            if any(keyword in bad_effects for keyword in ['자극', '알레르기', '트러블']):
                suitability['sensitive'] -= 0.4
        
        # 알레르기 위험 성분은 민감성 피부에 부적합
        if ingredient.is_allergy:
            suitability['sensitive'] -= 0.3
        
        # 0.0-1.0 범위로 제한
        for skin_type in suitability:
            suitability[skin_type] = max(0.0, min(1.0, suitability[skin_type]))
        
        return suitability
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보 반환"""
        return self.cache.cache.get_cache_info()
    
    async def clear_cache(self) -> int:
        """캐시 전체 삭제"""
        return self.cache.cache.clear()
    
    async def cleanup_expired_cache(self) -> int:
        """만료된 캐시 엔트리 정리"""
        return self.cache.cache.cleanup_expired()
    
    async def invalidate_product_cache(self, product_id: int) -> bool:
        """특정 제품의 캐시 무효화"""
        return self.cache.invalidate_product(product_id)
    
    async def get_top_cached_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """가장 많이 캐시된 제품 목록"""
        return self.cache.cache.get_top_accessed_keys(limit)