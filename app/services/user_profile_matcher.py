"""
사용자 프로필 매칭 시스템
연령대별, 피부타입별 특성을 정의하고 제품과 매칭하는 고도화된 개인화 엔진
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import json

logger = logging.getLogger(__name__)

@dataclass
class AgeProfile:
    """연령대별 피부 프로필"""
    age_group: str
    skin_concerns: List[str]
    beneficial_effects: List[str]
    harmful_effects: List[str]
    ingredient_preferences: Dict[str, float]
    purpose_weights: Dict[str, float]
    category_preferences: Dict[str, float]
    safety_threshold: float  # EWG 등급 허용 기준

@dataclass
class SkinTypeProfile:
    """피부타입별 프로필"""
    skin_type: str
    required_effects: List[str]
    avoid_effects: List[str]
    ingredient_preferences: Dict[str, float]
    safety_multiplier: float  # 안전성 가중치

@dataclass
class ProfileMatchResult:
    """프로필 매칭 결과"""
    product_id: int
    age_compatibility: float      # 0-100
    skin_type_compatibility: float # 0-100
    preference_compatibility: float # 0-100
    overall_personalization_score: float # 0-100
    rationales: List[str]
    safety_warnings: List[str] = field(default_factory=list)

class AgeProfiler:
    """연령대별 프로필 관리자"""
    
    def __init__(self):
        self.profiles = self._initialize_age_profiles()
    
    def _initialize_age_profiles(self) -> Dict[str, AgeProfile]:
        """연령대별 프로필 초기화 (피부과학 및 화장품학 기반)"""
        return {
            "10s": AgeProfile(
                age_group="10s",
                skin_concerns=["여드름", "과도한 피지", "모공", "트러블", "사춘기 호르몬"],
                beneficial_effects=[
                    "살균", "항염", "피지 조절", "진정", "수렴", 
                    "각질 제거", "모공 수축", "트러블 케어"
                ],
                harmful_effects=[
                    "피부 자극", "건조", "과도한 영양", "무거운 질감",
                    "강한 산", "레티놀", "고농도 활성성분"
                ],
                ingredient_preferences={
                    "salicylic_acid": 1.5,  # BHA
                    "tea_tree": 1.4,
                    "niacinamide": 1.3,
                    "zinc": 1.3,
                    "retinol": 0.2,  # 10대에는 부적합
                    "aha": 0.6,
                    "oil": 0.3
                },
                purpose_weights={
                    "피부 보호": 1.2,
                    "수렴 진정": 1.5,
                    "피부 보습": 1.0,
                    "안티에이징": 0.3
                },
                category_preferences={
                    "클렌저": 1.3,
                    "토너": 1.2,
                    "에센스": 0.8,
                    "크림": 0.9
                },
                safety_threshold=3.0  # EWG 3등급까지 허용
            ),
            
            "20s": AgeProfile(
                age_group="20s",
                skin_concerns=["여드름 흉터", "모공", "피지 조절", "예방 케어", "색소침착"],
                beneficial_effects=[
                    "각질 감소", "수분 흡수율 증가", "진정", "보습",
                    "미백", "항산화", "모공 관리", "피부 재생"
                ],
                harmful_effects=[
                    "피부 자극", "과도한 영양", "무거운 질감",
                    "강한 향료", "알코올"
                ],
                ingredient_preferences={
                    "vitamin_c": 1.4,
                    "niacinamide": 1.4,
                    "aha": 1.3,
                    "hyaluronic_acid": 1.2,
                    "retinol": 0.9,
                    "peptide": 0.8
                },
                purpose_weights={
                    "피부 보습": 1.3,
                    "피부 보호": 1.4,
                    "수렴 진정": 1.2,
                    "안티에이징": 0.8
                },
                category_preferences={
                    "세럼": 1.3,
                    "에센스": 1.2,
                    "선크림": 1.4,
                    "마스크": 1.1
                },
                safety_threshold=4.0
            ),
            
            "30s": AgeProfile(
                age_group="30s",
                skin_concerns=["초기 노화", "탄력 저하", "수분 부족", "잔주름", "피로한 피부"],
                beneficial_effects=[
                    "보습력 증가", "수분 증발 방지", "피부 탄력", "항산화",
                    "주름 개선", "피부 재생", "콜라겐 생성", "피부 장벽 강화"
                ],
                harmful_effects=[
                    "과도한 각질 제거", "강한 계면활성제", "알코올",
                    "자극적인 향료", "건조 성분"
                ],
                ingredient_preferences={
                    "retinol": 1.4,
                    "peptide": 1.4,
                    "hyaluronic_acid": 1.4,
                    "vitamin_c": 1.3,
                    "ceramide": 1.2,
                    "collagen": 1.2
                },
                purpose_weights={
                    "피부 보습": 1.5,
                    "피부 보호": 1.4,
                    "안티에이징": 1.4,
                    "수렴 진정": 1.1
                },
                category_preferences={
                    "세럼": 1.4,
                    "아이크림": 1.3,
                    "크림": 1.3,
                    "선크림": 1.4
                },
                safety_threshold=5.0
            ),
            
            "40s": AgeProfile(
                age_group="40s",
                skin_concerns=["주름", "탄력", "색소침착", "건조함", "호르몬 변화"],
                beneficial_effects=[
                    "보습력 증가", "수분 증발 방지", "피부 탄력", "재생",
                    "주름 개선", "미백", "콜라겐 생성", "피부 밀도 증가"
                ],
                harmful_effects=[
                    "피부 자극", "건조", "알코올", "강한 산",
                    "자극적인 성분", "과도한 각질 제거"
                ],
                ingredient_preferences={
                    "peptide": 1.5,
                    "retinol": 1.4,
                    "collagen": 1.4,
                    "ceramide": 1.4,
                    "hyaluronic_acid": 1.3,
                    "vitamin_e": 1.3
                },
                purpose_weights={
                    "피부 보습": 1.6,
                    "안티에이징": 1.5,
                    "피부 보호": 1.4,
                    "수렴 진정": 1.2
                },
                category_preferences={
                    "크림": 1.5,
                    "아이크림": 1.4,
                    "세럼": 1.4,
                    "마스크": 1.3
                },
                safety_threshold=6.0
            ),
            
            "50s": AgeProfile(
                age_group="50s",
                skin_concerns=["깊은 주름", "처짐", "색소침착", "극건조", "갱년기 피부"],
                beneficial_effects=[
                    "보습력 증가", "수분 증발 방지", "진정", "재생",
                    "주름 개선", "탄력 증진", "피부 밀도 증가", "호르몬 케어"
                ],
                harmful_effects=[
                    "피부 자극", "건조", "알코올", "강한 성분",
                    "자극적인 향료", "산성 성분", "각질 제거"
                ],
                ingredient_preferences={
                    "peptide": 1.6,
                    "ceramide": 1.5,
                    "squalane": 1.5,
                    "collagen": 1.5,
                    "hyaluronic_acid": 1.4,
                    "retinol": 1.0,  # 50대는 순한 레티놀만
                    "aha": 0.5,
                    "bha": 0.4
                },
                purpose_weights={
                    "피부 보습": 1.7,
                    "피부 보호": 1.5,
                    "수렴 진정": 1.4,
                    "안티에이징": 1.6
                },
                category_preferences={
                    "크림": 1.6,
                    "아이크림": 1.5,
                    "오일": 1.4,
                    "마스크": 1.4
                },
                safety_threshold=7.0  # 50대는 더 관대한 기준
            )
        }
    
    def get_profile(self, age_group: str) -> Optional[AgeProfile]:
        """연령대별 프로필 조회"""
        return self.profiles.get(age_group)
    
    def calculate_age_compatibility(
        self, 
        age_group: str, 
        ingredient_analysis: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """연령대별 적합성 점수 계산"""
        profile = self.get_profile(age_group)
        if not profile:
            return 50.0, [f"알 수 없는 연령대: {age_group}"]
        
        score = 50.0  # 기본 점수
        rationales = []
        
        # 1. 유익한 효과 분석
        beneficial_matches = 0
        key_ingredients = ingredient_analysis.get('key_ingredients', [])
        all_effects = ingredient_analysis.get('all_effects', {})
        
        for effect, count in all_effects.items():
            if any(benefit in effect for benefit in profile.beneficial_effects):
                # 주요 성분(상위 5개)에 포함된 경우 가중치 추가
                is_key_ingredient = any(
                    effect in ing.get('beneficial_effects', [])
                    for ing in key_ingredients
                )
                weight = 2.0 if is_key_ingredient else 1.0
                score += count * 6 * weight
                beneficial_matches += 1
                
                if beneficial_matches <= 2:  # 상위 2개만 근거로 추가
                    rationales.append(f"{age_group}에 유익한 '{effect}' 효과 포함")
        
        # 2. 해로운 효과 감점
        safety_concerns = ingredient_analysis.get('safety_concerns', [])
        harmful_matches = 0
        
        for concern in safety_concerns:
            if any(harm in concern for harm in profile.harmful_effects):
                # 주요 성분에 포함된 경우 더 큰 감점
                is_key_concern = any(
                    concern in ing.get('harmful_effects', [])
                    for ing in key_ingredients
                )
                penalty = -15 if is_key_concern else -8
                score += penalty
                harmful_matches += 1
                
                if harmful_matches <= 1:  # 1개만 경고로 추가
                    rationales.append(f"{age_group}에 부적합한 '{concern}' 부작용 감지")
        
        # 3. 성분 선호도 가중치 적용
        ingredient_bonus = 0
        for ingredient in key_ingredients:
            korean_name = ingredient.get('korean_name', '').lower()
            for pref_ingredient, weight in profile.ingredient_preferences.items():
                if pref_ingredient.replace('_', ' ') in korean_name or pref_ingredient in korean_name:
                    bonus = (weight - 1.0) * 10
                    ingredient_bonus += bonus
                    if bonus > 0:
                        rationales.append(f"{age_group}에 적합한 '{ingredient['korean_name']}' 성분")
                    break
        
        score += ingredient_bonus
        
        # 4. 안전성 기준 적용
        overall_safety = ingredient_analysis.get('overall_safety_score', 50.0)
        if overall_safety < profile.safety_threshold * 10:  # safety_threshold를 0-100 스케일로 변환
            safety_penalty = (profile.safety_threshold * 10 - overall_safety) * 0.5
            score -= safety_penalty
            rationales.append(f"{age_group} 안전성 기준 미달")
        
        # 최종 점수 정규화
        final_score = max(0.0, min(score, 100.0))
        
        return final_score, rationales[:3]  # 상위 3개 근거만 반환

class SkinTypeProfiler:
    """피부타입별 프로필 관리자"""
    
    def __init__(self):
        self.profiles = self._initialize_skin_type_profiles()
    
    def _initialize_skin_type_profiles(self) -> Dict[str, SkinTypeProfile]:
        """피부타입별 프로필 초기화"""
        return {
            "dry": SkinTypeProfile(
                skin_type="dry",
                required_effects=[
                    "보습력 증가", "수분 증발 방지", "강력 보습", 
                    "피부 장벽 강화", "수분 공급", "오일 공급"
                ],
                avoid_effects=[
                    "피부건조", "알코올", "수렴", "각질 제거",
                    "강한 계면활성제", "건조 성분"
                ],
                ingredient_preferences={
                    "hyaluronic_acid": 1.5,
                    "ceramide": 1.5,
                    "glycerin": 1.4,
                    "squalane": 1.4,
                    "shea_butter": 1.3,
                    "alcohol": 0.2,
                    "salicylic_acid": 0.4
                },
                safety_multiplier=1.2  # 건성 피부는 자극에 더 민감
            ),
            
            "oily": SkinTypeProfile(
                skin_type="oily",
                required_effects=[
                    "피지 조절", "수렴", "각질 감소", "모공 수축",
                    "유분 조절", "매트 효과", "블랙헤드 제거"
                ],
                avoid_effects=[
                    "과도한 유분", "무거운 질감", "코메도 유발",
                    "기름기", "끈적함"
                ],
                ingredient_preferences={
                    "salicylic_acid": 1.5,
                    "niacinamide": 1.4,
                    "zinc": 1.4,
                    "tea_tree": 1.3,
                    "clay": 1.3,
                    "oil": 0.3,
                    "heavy_cream": 0.4
                },
                safety_multiplier=0.9  # 지성 피부는 상대적으로 덜 민감
            ),
            
            "sensitive": SkinTypeProfile(
                skin_type="sensitive",
                required_effects=[
                    "수렴 및 진정", "예민현상 진정", "진정", "항염",
                    "알레르기 완화", "자극 완화", "피부 보호"
                ],
                avoid_effects=[
                    "피부 자극", "아로마오일", "향료", "알코올",
                    "강한 산", "각질 제거", "자극적인 성분"
                ],
                ingredient_preferences={
                    "centella": 1.6,
                    "aloe": 1.5,
                    "chamomile": 1.4,
                    "panthenol": 1.4,
                    "allantoin": 1.3,
                    "fragrance": 0.1,
                    "alcohol": 0.1,
                    "retinol": 0.3,
                    "aha": 0.2,
                    "bha": 0.3
                },
                safety_multiplier=1.5  # 민감성 피부는 안전성이 매우 중요
            ),
            
            "combination": SkinTypeProfile(
                skin_type="combination",
                required_effects=[
                    "균형", "수분", "가벼운", "부분 케어",
                    "T존 케어", "유수분 밸런스", "모공 관리"
                ],
                avoid_effects=[
                    "과도한 유분", "과도한 건조", "무거운 질감",
                    "극단적인 효과"
                ],
                ingredient_preferences={
                    "niacinamide": 1.4,
                    "hyaluronic_acid": 1.3,
                    "salicylic_acid": 1.2,
                    "vitamin_c": 1.2,
                    "heavy_oil": 0.5,
                    "strong_acid": 0.6
                },
                safety_multiplier=1.0  # 복합성 피부는 중간 수준
            )
        }
    
    def get_profile(self, skin_type: str) -> Optional[SkinTypeProfile]:
        """피부타입별 프로필 조회"""
        return self.profiles.get(skin_type)
    
    def calculate_skin_type_compatibility(
        self, 
        skin_type: str, 
        ingredient_analysis: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """피부타입별 적합성 점수 계산"""
        profile = self.get_profile(skin_type)
        if not profile:
            return 50.0, [f"알 수 없는 피부타입: {skin_type}"]
        
        score = 50.0  # 기본 점수
        rationales = []
        
        # 1. 필수 효능 매칭
        all_effects = ingredient_analysis.get('all_effects', {})
        required_matches = 0
        
        for effect, count in all_effects.items():
            if any(req in effect for req in profile.required_effects):
                score += count * 8
                required_matches += 1
                if required_matches <= 2:
                    rationales.append(f"{skin_type} 피부에 필요한 '{effect}' 효과")
        
        # 2. 회피 효능 감점
        safety_concerns = ingredient_analysis.get('safety_concerns', [])
        avoid_matches = 0
        
        for concern in safety_concerns:
            if any(avoid in concern for avoid in profile.avoid_effects):
                score -= 12
                avoid_matches += 1
                if avoid_matches <= 1:
                    rationales.append(f"{skin_type} 피부에 부적합한 '{concern}' 부작용")
        
        # 3. 성분 선호도 적용
        key_ingredients = ingredient_analysis.get('key_ingredients', [])
        for ingredient in key_ingredients:
            korean_name = ingredient.get('korean_name', '').lower()
            for pref_ingredient, weight in profile.ingredient_preferences.items():
                if pref_ingredient.replace('_', ' ') in korean_name:
                    bonus = (weight - 1.0) * 12
                    score += bonus
                    if bonus > 0:
                        rationales.append(f"{skin_type} 피부에 적합한 '{ingredient['korean_name']}'")
                    elif bonus < -5:
                        rationales.append(f"{skin_type} 피부에 부적합한 '{ingredient['korean_name']}'")
                    break
        
        # 4. 안전성 가중치 적용
        safety_score = ingredient_analysis.get('overall_safety_score', 50.0)
        adjusted_safety = safety_score * profile.safety_multiplier
        safety_bonus = (adjusted_safety - 50.0) * 0.3
        score += safety_bonus
        
        # 최종 점수 정규화
        final_score = max(0.0, min(score, 100.0))
        
        return final_score, rationales[:3]

class PreferenceProfiler:
    """개인 선호도 프로필 관리자"""
    
    def calculate_preference_compatibility(
        self, 
        user_preferences: Dict[str, Any], 
        product_data: Dict[str, Any],
        ingredient_analysis: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """개인 선호도 적합성 점수 계산"""
        score = 50.0  # 기본 점수
        rationales = []
        
        # 1. 브랜드 선호도
        preferred_brands = user_preferences.get('preferred_brands', [])
        brand_name = product_data.get('brand_name', '')
        
        if brand_name in preferred_brands:
            score += 25
            rationales.append(f"선호 브랜드 '{brand_name}'")
        
        # 2. 성분 선호도
        preferred_ingredients = user_preferences.get('preferred_ingredients', [])
        avoided_ingredients = user_preferences.get('avoided_ingredients', [])
        
        key_ingredients = ingredient_analysis.get('key_ingredients', [])
        
        for ingredient in key_ingredients:
            korean_name = ingredient.get('korean_name', '')
            
            # 선호 성분 확인
            for pref in preferred_ingredients:
                if pref.lower() in korean_name.lower():
                    score += 15
                    rationales.append(f"선호 성분 '{korean_name}' 포함")
                    break
            
            # 기피 성분 확인 (안전성 우선 정책)
            for avoid in avoided_ingredients:
                if avoid.lower() in korean_name.lower():
                    # 안전성이 높으면 감점을 줄임
                    safety_score = ingredient_analysis.get('overall_safety_score', 50.0)
                    if safety_score > 70:
                        penalty = -10  # 안전한 성분이면 적은 감점
                        rationales.append(f"기피 성분 '{korean_name}' 포함 (안전함)")
                    else:
                        penalty = -20  # 안전하지 않으면 큰 감점
                        rationales.append(f"기피 성분 '{korean_name}' 포함 (주의 필요)")
                    score += penalty
                    break
        
        # 3. 카테고리 선호도
        preferred_categories = user_preferences.get('preferred_categories', [])
        category = product_data.get('category_name', '')
        
        if category in preferred_categories:
            score += 10
            rationales.append(f"선호 카테고리 '{category}'")
        
        # 4. 과거 피드백 반영 (향후 확장)
        feedback_score = user_preferences.get('feedback_score', 0)
        if feedback_score != 0:
            score += feedback_score * 5
            if feedback_score > 0:
                rationales.append("과거 긍정적 피드백 반영")
            else:
                rationales.append("과거 부정적 피드백 반영")
        
        # 최종 점수 정규화
        final_score = max(0.0, min(score, 100.0))
        
        return final_score, rationales[:3]

class UserProfileMatcher:
    """사용자 프로필 매칭 시스템 메인 클래스"""
    
    def __init__(self):
        self.age_profiler = AgeProfiler()
        self.skin_type_profiler = SkinTypeProfiler()
        self.preference_profiler = PreferenceProfiler()
    
    async def match(
        self, 
        user_profile: Dict[str, Any], 
        ingredient_analysis: Dict[int, Dict[str, Any]],
        products_data: Dict[int, Dict[str, Any]]
    ) -> Dict[int, ProfileMatchResult]:
        """
        사용자 프로필과 제품들의 성분 분석 결과를 매칭하여 개인화 점수 계산
        
        Args:
            user_profile: 사용자 프로필 정보
            ingredient_analysis: 제품별 성분 분석 결과
            products_data: 제품 기본 정보
            
        Returns:
            제품별 프로필 매칭 결과
        """
        results = {}
        
        # 사용자 프로필 정보 추출
        age_group = user_profile.get('age_group')
        skin_type = user_profile.get('skin_type')
        preferences = user_profile.get('preferences', {})
        
        for product_id, analysis in ingredient_analysis.items():
            try:
                # 1. 연령 적합성 계산 (가중치 50%)
                if age_group:
                    age_score, age_rationales = self.age_profiler.calculate_age_compatibility(
                        age_group, analysis
                    )
                else:
                    age_score, age_rationales = 50.0, ["연령 정보 없음"]
                
                # 2. 피부타입 적합성 계산 (가중치 30%)
                if skin_type:
                    skin_score, skin_rationales = self.skin_type_profiler.calculate_skin_type_compatibility(
                        skin_type, analysis
                    )
                else:
                    skin_score, skin_rationales = 50.0, ["피부타입 정보 없음"]
                
                # 3. 개인 선호도 계산 (가중치 20%)
                product_data = products_data.get(product_id, {})
                if preferences:
                    pref_score, pref_rationales = self.preference_profiler.calculate_preference_compatibility(
                        preferences, product_data, analysis
                    )
                else:
                    pref_score, pref_rationales = 50.0, ["선호도 정보 없음"]
                
                # 4. 종합 개인화 점수 계산 (가중 평균)
                overall_score = (
                    age_score * 0.5 +      # 연령 적합성 50%
                    skin_score * 0.3 +     # 피부타입 적합성 30%
                    pref_score * 0.2       # 개인 선호도 20%
                )
                
                # 5. 추천 근거 생성
                rationales = self._generate_rationales(
                    age_group, skin_type, 
                    age_rationales, skin_rationales, pref_rationales,
                    age_score, skin_score, pref_score
                )
                
                # 6. 안전성 경고 생성
                safety_warnings = self._generate_safety_warnings(
                    user_profile, analysis
                )
                
                results[product_id] = ProfileMatchResult(
                    product_id=product_id,
                    age_compatibility=age_score,
                    skin_type_compatibility=skin_score,
                    preference_compatibility=pref_score,
                    overall_personalization_score=overall_score,
                    rationales=rationales,
                    safety_warnings=safety_warnings
                )
                
            except Exception as e:
                logger.error(f"프로필 매칭 실패 (product_id: {product_id}): {e}")
                # 실패 시 기본값 반환
                results[product_id] = ProfileMatchResult(
                    product_id=product_id,
                    age_compatibility=50.0,
                    skin_type_compatibility=50.0,
                    preference_compatibility=50.0,
                    overall_personalization_score=50.0,
                    rationales=["프로필 매칭 중 오류 발생"],
                    safety_warnings=["안전성 평가 불가"]
                )
        
        return results
    
    def _generate_rationales(
        self,
        age_group: Optional[str],
        skin_type: Optional[str],
        age_rationales: List[str],
        skin_rationales: List[str],
        pref_rationales: List[str],
        age_score: float,
        skin_score: float,
        pref_score: float
    ) -> List[str]:
        """추천 근거 자동 생성"""
        rationales = []
        
        # 점수가 높은 순서대로 근거 추가 (최대 3개)
        score_rationale_pairs = [
            (age_score, age_rationales, f"[{age_group}]" if age_group else "[연령]"),
            (skin_score, skin_rationales, f"[{skin_type}]" if skin_type else "[피부타입]"),
            (pref_score, pref_rationales, "[선호도]")
        ]
        
        # 점수 순으로 정렬
        score_rationale_pairs.sort(key=lambda x: x[0], reverse=True)
        
        for score, rationale_list, prefix in score_rationale_pairs:
            if score > 60 and rationale_list:  # 점수가 60 이상인 경우만
                for rationale in rationale_list[:1]:  # 각 카테고리에서 1개씩
                    if rationale and "정보 없음" not in rationale:
                        rationales.append(f"{prefix} {rationale}")
                        if len(rationales) >= 3:
                            break
            if len(rationales) >= 3:
                break
        
        # 근거가 부족한 경우 기본 근거 추가
        if len(rationales) == 0:
            if age_group and skin_type:
                rationales.append(f"{age_group} {skin_type} 피부에 적합한 제품")
            else:
                rationales.append("개인화 분석 결과 적합한 제품")
        
        return rationales[:3]  # 최대 3개까지만
    
    def _generate_safety_warnings(
        self,
        user_profile: Dict[str, Any],
        ingredient_analysis: Dict[str, Any]
    ) -> List[str]:
        """안전성 경고 메시지 생성"""
        warnings = []
        
        age_group = user_profile.get('age_group')
        skin_type = user_profile.get('skin_type')
        safety_concerns = ingredient_analysis.get('safety_concerns', [])
        key_ingredients = ingredient_analysis.get('key_ingredients', [])
        overall_safety = ingredient_analysis.get('overall_safety_score', 50.0)
        
        # 1. 연령별 위험 성분 체크
        if age_group:
            age_profile = self.age_profiler.get_profile(age_group)
            if age_profile:
                for ingredient in key_ingredients:
                    korean_name = ingredient.get('korean_name', '')
                    harmful_effects = ingredient.get('harmful_effects', [])
                    
                    for harmful in harmful_effects:
                        if any(harm in harmful for harm in age_profile.harmful_effects):
                            warnings.append(f"{age_group}에 부적합한 '{korean_name}' 성분 포함")
                            break
        
        # 2. 피부타입별 위험 성분 체크
        if skin_type:
            skin_profile = self.skin_type_profiler.get_profile(skin_type)
            if skin_profile:
                for ingredient in key_ingredients:
                    korean_name = ingredient.get('korean_name', '')
                    harmful_effects = ingredient.get('harmful_effects', [])
                    
                    for harmful in harmful_effects:
                        if any(avoid in harmful for avoid in skin_profile.avoid_effects):
                            warnings.append(f"{skin_type} 피부에 자극 가능한 '{korean_name}' 성분")
                            break
        
        # 3. 전체 안전성 점수 기반 경고
        if overall_safety < 30:
            warnings.append("전반적인 안전성이 낮은 제품입니다")
        elif overall_safety < 50:
            warnings.append("일부 성분에 주의가 필요합니다")
        
        # 4. 고위험 성분 체크 (EWG 등급 기반)
        high_risk_ingredients = []
        for ingredient in key_ingredients:
            ewg_grade = ingredient.get('ewg_grade')
            if ewg_grade and ewg_grade in ['8', '9', '10']:
                high_risk_ingredients.append(ingredient.get('korean_name', ''))
        
        if high_risk_ingredients:
            warnings.append(f"고위험 성분 포함: {', '.join(high_risk_ingredients[:2])}")
        
        return warnings[:2]  # 최대 2개 경고까지만
    
    def get_profile_summary(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 프로필 요약 정보 반환"""
        age_group = user_profile.get('age_group')
        skin_type = user_profile.get('skin_type')
        
        summary = {
            'age_group': age_group,
            'skin_type': skin_type,
            'age_profile': None,
            'skin_profile': None
        }
        
        if age_group:
            age_profile = self.age_profiler.get_profile(age_group)
            if age_profile:
                summary['age_profile'] = {
                    'concerns': age_profile.skin_concerns,
                    'beneficial_effects': age_profile.beneficial_effects[:5],
                    'harmful_effects': age_profile.harmful_effects[:5]
                }
        
        if skin_type:
            skin_profile = self.skin_type_profiler.get_profile(skin_type)
            if skin_profile:
                summary['skin_profile'] = {
                    'required_effects': skin_profile.required_effects[:5],
                    'avoid_effects': skin_profile.avoid_effects[:5]
                }
        
        return summary