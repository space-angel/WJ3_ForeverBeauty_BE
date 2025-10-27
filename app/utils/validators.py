"""
입력 검증 유틸리티 (Validators)
추천 요청 검증 및 비즈니스 로직 검증
"""
from typing import List, Dict, Optional, Any, Tuple
from app.models.request import RecommendationRequest
from app.utils.alias_mapper import AliasMapper
import re
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """검증 오류"""
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)

class RequestValidator:
    """요청 검증 클래스"""
    
    def __init__(self):
        self.alias_mapper = AliasMapper()
        
        # ATC 코드 패턴 (기본적인 형식 검증)
        self.atc_pattern = re.compile(r'^[A-Z]\d{2}([A-Z]{2}(\d{2})?)?$')
        
        # 허용된 의도 태그 (확장 가능)
        self.allowed_intent_tags = {
            '보습', '수분', '진정', '브라이트닝', '미백', '주름개선', '안티에이징',
            '모공케어', '각질케어', '트러블케어', '민감성', '유분조절', '탄력',
            '자외선차단', '선케어', '아이케어', '립케어', '바디케어', '세정',
            '클렌징', '토너', '에센스', '세럼', '크림', '로션', '오일', '밤',
            '마스크', '팩', '스크럽', '필링', '선크림', '파운데이션', '컨실러'
        }
        
        # 허용된 카테고리 (확장 가능)
        self.allowed_categories = {
            '클렌저', '토너', '에센스', '세럼', '앰플', '로션', '에멀젼', '크림',
            '오일', '밤', '마스크', '팩', '스크럽', '필링', '선크림', '선케어',
            '아이크림', '립밤', '립스틱', '파운데이션', '컨실러', '파우더',
            '블러셔', '아이섀도', '마스카라', '아이라이너', '브로우'
        }
    
    def validate_request(self, request: RecommendationRequest) -> List[ValidationError]:
        """
        전체 요청 검증
        """
        errors = []
        
        # 의도 태그 검증
        errors.extend(self._validate_intent_tags(request.intent_tags))
        
        # 카테고리 검증
        errors.extend(self._validate_category(request.category_like))
        
        # 사용 맥락 검증
        errors.extend(self._validate_use_context(request.use_context))
        
        # 의약품 프로필 검증
        errors.extend(self._validate_med_profile(request.med_profile))
        
        # 가격 범위 검증
        errors.extend(self._validate_price_range(request.price))
        
        # top_n 검증
        errors.extend(self._validate_top_n(request.top_n))
        
        # 비즈니스 로직 검증
        errors.extend(self._validate_business_logic(request))
        
        return errors
    
    def _validate_intent_tags(self, intent_tags: List[str]) -> List[ValidationError]:
        """의도 태그 검증"""
        errors = []
        
        if not intent_tags:
            return errors  # 빈 리스트는 허용
        
        if len(intent_tags) > 10:
            errors.append(ValidationError(
                "의도 태그는 최대 10개까지 허용됩니다",
                field="intent_tags",
                code="TOO_MANY_INTENT_TAGS"
            ))
        
        for i, tag in enumerate(intent_tags):
            if not isinstance(tag, str):
                errors.append(ValidationError(
                    f"의도 태그는 문자열이어야 합니다: {tag}",
                    field=f"intent_tags[{i}]",
                    code="INVALID_INTENT_TAG_TYPE"
                ))
                continue
            
            if len(tag.strip()) == 0:
                errors.append(ValidationError(
                    "빈 의도 태그는 허용되지 않습니다",
                    field=f"intent_tags[{i}]",
                    code="EMPTY_INTENT_TAG"
                ))
                continue
            
            if len(tag) > 20:
                errors.append(ValidationError(
                    f"의도 태그가 너무 깁니다 (최대 20자): {tag}",
                    field=f"intent_tags[{i}]",
                    code="INTENT_TAG_TOO_LONG"
                ))
            
            # 허용된 태그 검증 (경고 수준)
            if tag.strip() not in self.allowed_intent_tags:
                logger.warning(f"알려지지 않은 의도 태그: {tag}")
        
        return errors
    
    def _validate_category(self, category_like: Optional[str]) -> List[ValidationError]:
        """카테고리 검증"""
        errors = []
        
        if category_like is None:
            return errors  # None은 허용
        
        if not isinstance(category_like, str):
            errors.append(ValidationError(
                "카테고리는 문자열이어야 합니다",
                field="category_like",
                code="INVALID_CATEGORY_TYPE"
            ))
            return errors
        
        if len(category_like.strip()) == 0:
            errors.append(ValidationError(
                "빈 카테고리는 허용되지 않습니다",
                field="category_like",
                code="EMPTY_CATEGORY"
            ))
        
        if len(category_like) > 50:
            errors.append(ValidationError(
                "카테고리명이 너무 깁니다 (최대 50자)",
                field="category_like",
                code="CATEGORY_TOO_LONG"
            ))
        
        return errors
    
    def _validate_use_context(self, use_context) -> List[ValidationError]:
        """사용 맥락 검증"""
        errors = []
        
        # Pydantic이 이미 타입 검증을 했으므로 비즈니스 로직만 검증
        
        # 논리적 모순 검증
        if use_context.day_use and not use_context.leave_on:
            logger.warning("주간 사용이지만 리브온이 아닌 제품: 자외선 노출 위험 고려 필요")
        
        if use_context.large_area_hint and use_context.face:
            logger.info("얼굴과 넓은 부위 동시 사용: 전신 제품 고려")
        
        return errors
    
    def _validate_med_profile(self, med_profile) -> List[ValidationError]:
        """의약품 프로필 검증"""
        errors = []
        
        # 의약품 코드 검증
        for i, code in enumerate(med_profile.codes):
            if not isinstance(code, str):
                errors.append(ValidationError(
                    f"의약품 코드는 문자열이어야 합니다: {code}",
                    field=f"med_profile.codes[{i}]",
                    code="INVALID_MED_CODE_TYPE"
                ))
                continue
            
            # MULTI 별칭 검증
            if code.startswith("MULTI:"):
                if not self.alias_mapper.validate_alias(code):
                    errors.append(ValidationError(
                        f"지원되지 않는 MULTI 별칭: {code}",
                        field=f"med_profile.codes[{i}]",
                        code="UNSUPPORTED_MULTI_ALIAS"
                    ))
            else:
                # ATC 코드 형식 검증
                if not self.atc_pattern.match(code):
                    errors.append(ValidationError(
                        f"잘못된 ATC 코드 형식: {code}",
                        field=f"med_profile.codes[{i}]",
                        code="INVALID_ATC_FORMAT"
                    ))
        
        # 중복 코드 검증
        if len(med_profile.codes) != len(set(med_profile.codes)):
            errors.append(ValidationError(
                "중복된 의약품 코드가 있습니다",
                field="med_profile.codes",
                code="DUPLICATE_MED_CODES"
            ))
        
        # 너무 많은 코드
        if len(med_profile.codes) > 20:
            errors.append(ValidationError(
                "의약품 코드는 최대 20개까지 허용됩니다",
                field="med_profile.codes",
                code="TOO_MANY_MED_CODES"
            ))
        
        return errors
    
    def _validate_price_range(self, price_range) -> List[ValidationError]:
        """가격 범위 검증"""
        errors = []
        
        # Pydantic이 이미 기본 검증을 했으므로 비즈니스 로직만 검증
        
        if price_range.min_price is not None and price_range.min_price < 0:
            errors.append(ValidationError(
                "최소 가격은 0 이상이어야 합니다",
                field="price.min_price",
                code="NEGATIVE_MIN_PRICE"
            ))
        
        if price_range.max_price is not None and price_range.max_price < 0:
            errors.append(ValidationError(
                "최대 가격은 0 이상이어야 합니다",
                field="price.max_price",
                code="NEGATIVE_MAX_PRICE"
            ))
        
        # 비현실적인 가격 범위
        if price_range.min_price is not None and price_range.min_price > 1000000:
            errors.append(ValidationError(
                "최소 가격이 너무 높습니다 (100만원 초과)",
                field="price.min_price",
                code="UNREALISTIC_MIN_PRICE"
            ))
        
        if price_range.max_price is not None and price_range.max_price > 1000000:
            errors.append(ValidationError(
                "최대 가격이 너무 높습니다 (100만원 초과)",
                field="price.max_price",
                code="UNREALISTIC_MAX_PRICE"
            ))
        
        return errors
    
    def _validate_top_n(self, top_n: int) -> List[ValidationError]:
        """top_n 검증"""
        errors = []
        
        # Pydantic이 이미 범위 검증을 했으므로 추가 검증은 불필요
        
        return errors
    
    def _validate_business_logic(self, request: RecommendationRequest) -> List[ValidationError]:
        """비즈니스 로직 검증"""
        errors = []
        
        # 임신/수유 + 특정 의도 태그 조합 경고
        if request.med_profile.preg_lact:
            risky_tags = {'각질케어', '필링', '레티놀', '화학적각질제거'}
            user_risky_tags = set(request.intent_tags) & risky_tags
            
            if user_risky_tags:
                logger.warning(f"임신/수유 중 위험한 의도 태그: {user_risky_tags}")
        
        # 얼굴 + 주간 사용 + 특정 의도 태그
        if request.use_context.face and request.use_context.day_use:
            photosensitive_tags = {'각질케어', 'AHA', 'BHA', '필링'}
            user_photosensitive_tags = set(request.intent_tags) & photosensitive_tags
            
            if user_photosensitive_tags:
                logger.warning(f"얼굴 주간 사용 시 광감작 위험 태그: {user_photosensitive_tags}")
        
        # 의약품 코드 중복 확장 검증
        if len(request.med_profile.codes) > 1:
            overlap_analysis = self.alias_mapper.get_overlap_analysis(request.med_profile.codes)
            
            if overlap_analysis['has_overlaps']:
                logger.info(f"의약품 코드 중복: {overlap_analysis['overlaps']}")
        
        return errors
    
    def validate_and_sanitize(self, request: RecommendationRequest) -> Tuple[RecommendationRequest, List[ValidationError]]:
        """
        검증 및 정제
        """
        errors = self.validate_request(request)
        
        # 정제 작업
        sanitized_request = self._sanitize_request(request)
        
        return sanitized_request, errors
    
    def _sanitize_request(self, request: RecommendationRequest) -> RecommendationRequest:
        """
        요청 데이터 정제
        """
        # 의도 태그 정제
        sanitized_intent_tags = []
        for tag in request.intent_tags:
            clean_tag = tag.strip()
            if clean_tag and clean_tag not in sanitized_intent_tags:
                sanitized_intent_tags.append(clean_tag)
        
        # 카테고리 정제
        sanitized_category = None
        if request.category_like:
            sanitized_category = request.category_like.strip()
            if not sanitized_category:
                sanitized_category = None
        
        # 의약품 코드 정제 (중복 제거, 대문자 변환)
        sanitized_med_codes = []
        for code in request.med_profile.codes:
            clean_code = code.strip().upper()
            if clean_code and clean_code not in sanitized_med_codes:
                sanitized_med_codes.append(clean_code)
        
        # 새로운 요청 객체 생성 (불변성 유지)
        sanitized_request = RecommendationRequest(
            intent_tags=sanitized_intent_tags,
            category_like=sanitized_category,
            use_context=request.use_context,
            med_profile=request.med_profile.model_copy(update={'codes': sanitized_med_codes}),
            price=request.price,
            top_n=request.top_n
        )
        
        return sanitized_request
    
    def get_validation_summary(self, errors: List[ValidationError]) -> Dict[str, Any]:
        """검증 결과 요약"""
        if not errors:
            return {
                'is_valid': True,
                'error_count': 0,
                'errors': []
            }
        
        error_by_field = {}
        error_by_code = {}
        
        for error in errors:
            # 필드별 그룹화
            field = error.field or 'general'
            if field not in error_by_field:
                error_by_field[field] = []
            error_by_field[field].append(error.message)
            
            # 코드별 그룹화
            code = error.code or 'UNKNOWN'
            error_by_code[code] = error_by_code.get(code, 0) + 1
        
        return {
            'is_valid': False,
            'error_count': len(errors),
            'errors': [{'field': e.field, 'message': e.message, 'code': e.code} for e in errors],
            'errors_by_field': error_by_field,
            'errors_by_code': error_by_code
        }
    
    def close(self):
        """리소스 정리"""
        if self.alias_mapper:
            self.alias_mapper.close()