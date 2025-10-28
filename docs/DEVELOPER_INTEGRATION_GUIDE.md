# 🛠️ 개발자를 위한 API 통합 가이드

## 🎯 개요

화장품 추천 API의 완전한 통합 가이드입니다. 
프론트엔드 개발자가 바로 사용할 수 있는 실용적인 예제와 베스트 프랙티스를 제공합니다.

---

## 🔌 API 기본 정보

### **📡 엔드포인트**
```
Base URL: http://localhost:8000
API Version: v1
Content-Type: application/json
```

### **🎯 주요 엔드포인트**
```
POST /api/v1/recommend              # 메인 추천 API
GET  /api/v1/recommend/health       # 헬스체크
GET  /api/v1/recommend/categories   # 지원 카테고리
GET  /api/v1/recommend/intent-tags  # 지원 의도 태그
```

---

## 🚀 빠른 시작

### **⚡ 1분 만에 시작하기**

```javascript
// 1. 가장 간단한 요청
const getRecommendations = async () => {
  const response = await fetch('http://localhost:8000/api/v1/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      intent_tags: ['moisturizing', 'anti-aging'],
      top_n: 5
    })
  });
  
  const data = await response.json();
  console.log('추천 결과:', data.recommendations);
};

// 2. 실행
getRecommendations();
```

### **📱 React Hook 예시**
```jsx
import { useState, useEffect } from 'react';

const useRecommendations = () => {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const getRecommendations = async (requestData) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      setRecommendations(data.recommendations);
      return data;
      
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { recommendations, loading, error, getRecommendations };
};

// 사용 예시
const RecommendationComponent = () => {
  const { recommendations, loading, error, getRecommendations } = useRecommendations();
  
  const handleRecommend = () => {
    getRecommendations({
      intent_tags: ['moisturizing'],
      top_n: 5
    });
  };

  if (loading) return <div>추천 분석 중...</div>;
  if (error) return <div>오류: {error}</div>;
  
  return (
    <div>
      <button onClick={handleRecommend}>추천받기</button>
      {recommendations.map(item => (
        <div key={item.product_id}>
          <h3>{item.product_name}</h3>
          <p>점수: {item.final_score}</p>
        </div>
      ))}
    </div>
  );
};
```

---

## 📋 요청 데이터 구조

### **🔥 필수 파라미터**
```typescript
interface MinimalRequest {
  intent_tags: string[];  // 필수! 최소 1개
  top_n?: number;        // 선택, 기본값 5
}

// 예시
const minimalRequest: MinimalRequest = {
  intent_tags: ['moisturizing', 'anti-aging']
};
```

### **⭐ 완전한 요청 구조**
```typescript
interface FullRecommendationRequest {
  // 필수
  intent_tags: string[];
  
  // 사용자 프로필 (선택)
  user_profile?: {
    age_group?: '10s' | '20s' | '30s' | '40s' | '50s' | '60s+';
    gender?: 'male' | 'female' | 'other';
    skin_type?: 'dry' | 'oily' | 'combination' | 'sensitive' | 'normal';
    skin_concerns?: string[];
    allergies?: string[];
  };
  
  // 의약품 정보 (선택)
  medications?: Array<{
    name: string;
    active_ingredients?: string[];
    usage_frequency?: string;
    dosage?: string;
  }>;
  
  // 사용 맥락 (선택)
  usage_context?: {
    season?: 'spring' | 'summer' | 'autumn' | 'winter';
    time_of_day?: 'morning' | 'afternoon' | 'evening' | 'night';
    occasion?: 'daily' | 'special' | 'work' | 'date';
    climate?: 'humid' | 'dry' | 'hot' | 'cold';
  };
  
  // 필터링 옵션 (선택)
  price_range?: {
    min?: number;
    max?: number;
  };
  categories?: string[];
  brands?: string[];
  exclude_ingredients?: string[];
  
  // 기타 옵션
  top_n?: number;                    // 1-20, 기본값 5
  include_reasoning?: boolean;       // 기본값 true
}
```

### **🎯 의도 태그 매핑**
```javascript
// 사용자 친화적 텍스트 → API 태그 매핑
const INTENT_MAPPING = {
  '건조함, 보습이 필요해요': 'moisturizing',
  '주름, 노화가 걱정돼요': 'anti-aging',
  '여드름, 트러블이 있어요': 'acne-care',
  '피부 톤업하고 싶어요': 'brightening',
  '민감성 피부예요': 'sensitive-care',
  '모공이 신경 쓰여요': 'pore-care',
  '피부 진정이 필요해요': 'soothing',
  '각질 제거하고 싶어요': 'exfoliating',
  '자외선 차단하고 싶어요': 'sun-protection',
  '유분 조절하고 싶어요': 'oil-control'
};

// 사용 예시
const userSelections = ['건조함, 보습이 필요해요', '주름, 노화가 걱정돼요'];
const intentTags = userSelections.map(selection => INTENT_MAPPING[selection]);
// 결과: ['moisturizing', 'anti-aging']
```

---

## 📤 응답 데이터 구조

### **✅ 성공 응답**
```typescript
interface RecommendationResponse {
  execution_summary: {
    request_id: string;
    timestamp: string;
    success: boolean;
    execution_time_seconds: number;
    ruleset_version: string;
    active_rules_count: number;
  };
  
  input_summary: {
    intent_tags_count: number;
    requested_count: number;
    has_user_profile: boolean;
    medications_count: number;
    has_usage_context: boolean;
    price_range_specified: boolean;
  };
  
  pipeline_statistics: {
    total_candidates: number;
    excluded_by_rules: number;
    penalized_products: number;
    final_recommendations: number;
    eligibility_rules_applied: number;
    scoring_rules_applied: number;
    query_time_ms: number;
    evaluation_time_ms: number;
    ranking_time_ms: number;
    total_time_ms: number;
  };
  
  recommendations: Array<{
    rank: number;
    product_id: string;
    product_name: string;
    brand_name: string;
    category: string;
    final_score: number;        // 0-100
    intent_match_score: number; // 0-100
    reasons: string[];
    warnings: string[];
    rule_hits: Array<{
      type: string;
      rule_id: string;
      weight: number;
      rationale_ko: string;
      citation_url?: string;
    }>;
  }>;
}
```

### **❌ 에러 응답**
```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    field?: string;
    details?: Record<string, any>;
  };
  timestamp: string;
  path: string;
}

// 주요 에러 코드
const ERROR_CODES = {
  'VALIDATION_ERROR': '입력 데이터 검증 실패',
  'RECOMMENDATION_ERROR': '추천 처리 중 오류',
  'INTERNAL_SERVER_ERROR': '서버 내부 오류'
};
```

---

## 🛠️ 실용적인 유틸리티 함수들

### **🔧 API 클라이언트 클래스**
```javascript
class RecommendationAPI {
  constructor(baseURL = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: { 'Content-Type': 'application/json' },
      ...options
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error?.message || `HTTP ${response.status}`);
      }

      return data;
    } catch (error) {
      console.error('API 요청 실패:', error);
      throw error;
    }
  }

  // 메인 추천 API
  async getRecommendations(requestData) {
    return this.request('/api/v1/recommend', {
      method: 'POST',
      body: JSON.stringify(requestData)
    });
  }

  // 헬스체크
  async checkHealth(includeStats = false) {
    return this.request(`/api/v1/recommend/health?include_stats=${includeStats}`);
  }

  // 지원 의도 태그 목록
  async getSupportedIntentTags() {
    return this.request('/api/v1/recommend/intent-tags');
  }

  // 지원 카테고리 목록
  async getSupportedCategories() {
    return this.request('/api/v1/recommend/categories');
  }
}

// 사용 예시
const api = new RecommendationAPI();

// 추천 요청
const recommendations = await api.getRecommendations({
  intent_tags: ['moisturizing'],
  top_n: 5
});

// 헬스체크
const health = await api.checkHealth(true);
```

### **🎯 요청 빌더 패턴**
```javascript
class RecommendationRequestBuilder {
  constructor() {
    this.request = {
      intent_tags: [],
      top_n: 5
    };
  }

  // 의도 태그 설정
  withIntents(intents) {
    this.request.intent_tags = Array.isArray(intents) ? intents : [intents];
    return this;
  }

  // 사용자 프로필 설정
  withProfile(profile) {
    this.request.user_profile = profile;
    return this;
  }

  // 의약품 정보 설정
  withMedications(medications) {
    this.request.medications = medications;
    return this;
  }

  // 가격 범위 설정
  withPriceRange(min, max) {
    this.request.price_range = { min, max };
    return this;
  }

  // 추천 개수 설정
  withTopN(n) {
    this.request.top_n = Math.max(1, Math.min(20, n));
    return this;
  }

  // 요청 객체 반환
  build() {
    if (this.request.intent_tags.length === 0) {
      throw new Error('의도 태그가 필요합니다');
    }
    return { ...this.request };
  }
}

// 사용 예시
const request = new RecommendationRequestBuilder()
  .withIntents(['moisturizing', 'anti-aging'])
  .withProfile({
    age_group: '30s',
    skin_type: 'dry'
  })
  .withPriceRange(20000, 80000)
  .withTopN(10)
  .build();

const recommendations = await api.getRecommendations(request);
```

### **⚡ 캐싱 및 성능 최적화**
```javascript
class CachedRecommendationAPI extends RecommendationAPI {
  constructor(baseURL, cacheTimeout = 5 * 60 * 1000) { // 5분 캐시
    super(baseURL);
    this.cache = new Map();
    this.cacheTimeout = cacheTimeout;
  }

  _getCacheKey(requestData) {
    return JSON.stringify(requestData);
  }

  _isValidCache(cacheEntry) {
    return Date.now() - cacheEntry.timestamp < this.cacheTimeout;
  }

  async getRecommendations(requestData) {
    const cacheKey = this._getCacheKey(requestData);
    const cached = this.cache.get(cacheKey);

    // 캐시 히트
    if (cached && this._isValidCache(cached)) {
      console.log('캐시에서 결과 반환');
      return cached.data;
    }

    // API 호출
    try {
      const data = await super.getRecommendations(requestData);
      
      // 캐시 저장
      this.cache.set(cacheKey, {
        data,
        timestamp: Date.now()
      });

      return data;
    } catch (error) {
      // 에러 시 오래된 캐시라도 반환
      if (cached) {
        console.warn('API 오류, 오래된 캐시 반환');
        return cached.data;
      }
      throw error;
    }
  }

  clearCache() {
    this.cache.clear();
  }
}
```

---

## 🚨 에러 처리 베스트 프랙티스

### **🛡️ 포괄적인 에러 처리**
```javascript
class RecommendationService {
  constructor() {
    this.api = new RecommendationAPI();
    this.retryCount = 3;
    this.retryDelay = 1000; // 1초
  }

  async getRecommendationsWithRetry(requestData, attempt = 1) {
    try {
      return await this.api.getRecommendations(requestData);
    } catch (error) {
      console.error(`추천 요청 실패 (시도 ${attempt}/${this.retryCount}):`, error);

      // 재시도 로직
      if (attempt < this.retryCount && this._isRetryableError(error)) {
        console.log(`${this.retryDelay}ms 후 재시도...`);
        await this._delay(this.retryDelay);
        return this.getRecommendationsWithRetry(requestData, attempt + 1);
      }

      // 사용자 친화적 에러 메시지
      throw new Error(this._getUserFriendlyErrorMessage(error));
    }
  }

  _isRetryableError(error) {
    // 네트워크 오류나 서버 오류는 재시도
    return error.message.includes('fetch') || 
           error.message.includes('500') ||
           error.message.includes('502') ||
           error.message.includes('503');
  }

  _getUserFriendlyErrorMessage(error) {
    if (error.message.includes('의도 태그')) {
      return '선택하신 옵션에 문제가 있어요. 다시 선택해주세요.';
    }
    if (error.message.includes('네트워크') || error.message.includes('fetch')) {
      return '인터넷 연결을 확인해주세요.';
    }
    if (error.message.includes('500')) {
      return '잠시 후 다시 시도해주세요.';
    }
    return '오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
  }

  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// 사용 예시
const service = new RecommendationService();

try {
  const recommendations = await service.getRecommendationsWithRetry({
    intent_tags: ['moisturizing'],
    top_n: 5
  });
  console.log('추천 성공:', recommendations);
} catch (error) {
  console.error('최종 실패:', error.message);
  // 사용자에게 친화적인 에러 메시지 표시
}
```

### **📱 React 에러 바운더리**
```jsx
class RecommendationErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('추천 컴포넌트 오류:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-fallback">
          <h3>추천 서비스에 일시적인 문제가 발생했어요</h3>
          <p>잠시 후 다시 시도해주세요.</p>
          <button onClick={() => window.location.reload()}>
            새로고침
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// 사용
<RecommendationErrorBoundary>
  <RecommendationComponent />
</RecommendationErrorBoundary>
```

---

## 🧪 테스트 가이드

### **🔍 단위 테스트 예시**
```javascript
// Jest 테스트 예시
describe('RecommendationAPI', () => {
  let api;

  beforeEach(() => {
    api = new RecommendationAPI('http://localhost:8000');
  });

  test('기본 추천 요청이 성공해야 함', async () => {
    const request = {
      intent_tags: ['moisturizing'],
      top_n: 3
    };

    const response = await api.getRecommendations(request);

    expect(response).toHaveProperty('recommendations');
    expect(response.recommendations).toHaveLength(3);
    expect(response.recommendations[0]).toHaveProperty('product_name');
    expect(response.recommendations[0]).toHaveProperty('final_score');
  });

  test('잘못된 의도 태그로 요청 시 에러가 발생해야 함', async () => {
    const request = {
      intent_tags: ['invalid_tag'],
      top_n: 3
    };

    await expect(api.getRecommendations(request))
      .rejects
      .toThrow('지원하지 않는 의도 태그');
  });

  test('헬스체크가 정상 작동해야 함', async () => {
    const health = await api.checkHealth();

    expect(health).toHaveProperty('status');
    expect(health.status).toBe('healthy');
  });
});
```

### **🎯 통합 테스트 예시**
```javascript
describe('추천 플로우 통합 테스트', () => {
  test('전체 추천 플로우가 정상 작동해야 함', async () => {
    const service = new RecommendationService();

    // 1. 지원 태그 조회
    const supportedTags = await service.api.getSupportedIntentTags();
    expect(supportedTags).toContain('moisturizing');

    // 2. 추천 요청
    const request = {
      intent_tags: ['moisturizing', 'anti-aging'],
      user_profile: {
        age_group: '30s',
        skin_type: 'dry'
      },
      top_n: 5
    };

    const response = await service.getRecommendationsWithRetry(request);

    // 3. 응답 검증
    expect(response.recommendations).toHaveLength(5);
    expect(response.execution_summary.success).toBe(true);
    expect(response.pipeline_statistics.total_candidates).toBeGreaterThan(0);

    // 4. 추천 품질 검증
    const firstRecommendation = response.recommendations[0];
    expect(firstRecommendation.final_score).toBeGreaterThan(50);
    expect(firstRecommendation.reasons).toHaveLength.greaterThan(0);
  });
});
```

---

## 📊 성능 모니터링

### **⚡ 성능 측정 유틸리티**
```javascript
class PerformanceMonitor {
  constructor() {
    this.metrics = [];
  }

  async measureAPICall(apiCall, label = 'API Call') {
    const startTime = performance.now();
    
    try {
      const result = await apiCall();
      const endTime = performance.now();
      const duration = endTime - startTime;

      this.metrics.push({
        label,
        duration,
        success: true,
        timestamp: new Date().toISOString()
      });

      console.log(`${label} 완료: ${duration.toFixed(2)}ms`);
      return result;

    } catch (error) {
      const endTime = performance.now();
      const duration = endTime - startTime;

      this.metrics.push({
        label,
        duration,
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      });

      console.error(`${label} 실패: ${duration.toFixed(2)}ms - ${error.message}`);
      throw error;
    }
  }

  getAverageResponseTime() {
    const successfulCalls = this.metrics.filter(m => m.success);
    if (successfulCalls.length === 0) return 0;
    
    const totalTime = successfulCalls.reduce((sum, m) => sum + m.duration, 0);
    return totalTime / successfulCalls.length;
  }

  getSuccessRate() {
    if (this.metrics.length === 0) return 0;
    const successCount = this.metrics.filter(m => m.success).length;
    return (successCount / this.metrics.length) * 100;
  }

  getMetricsSummary() {
    return {
      totalCalls: this.metrics.length,
      successRate: this.getSuccessRate(),
      averageResponseTime: this.getAverageResponseTime(),
      recentMetrics: this.metrics.slice(-10)
    };
  }
}

// 사용 예시
const monitor = new PerformanceMonitor();
const api = new RecommendationAPI();

const recommendations = await monitor.measureAPICall(
  () => api.getRecommendations({
    intent_tags: ['moisturizing'],
    top_n: 5
  }),
  '보습 제품 추천'
);

console.log('성능 요약:', monitor.getMetricsSummary());
```

---

## 🎯 프로덕션 배포 가이드

### **🔒 환경 설정**
```javascript
// config.js
const config = {
  development: {
    API_BASE_URL: 'http://localhost:8000',
    CACHE_TIMEOUT: 5 * 60 * 1000, // 5분
    RETRY_COUNT: 3,
    LOG_LEVEL: 'debug'
  },
  production: {
    API_BASE_URL: 'https://api.cosmetic-recommend.com',
    CACHE_TIMEOUT: 15 * 60 * 1000, // 15분
    RETRY_COUNT: 5,
    LOG_LEVEL: 'error'
  }
};

export default config[process.env.NODE_ENV || 'development'];
```

### **📈 로깅 및 모니터링**
```javascript
class Logger {
  constructor(level = 'info') {
    this.level = level;
    this.levels = { debug: 0, info: 1, warn: 2, error: 3 };
  }

  log(level, message, data = {}) {
    if (this.levels[level] >= this.levels[this.level]) {
      console[level](`[${new Date().toISOString()}] ${message}`, data);
      
      // 프로덕션에서는 외부 로깅 서비스로 전송
      if (process.env.NODE_ENV === 'production' && level === 'error') {
        this.sendToLoggingService(level, message, data);
      }
    }
  }

  debug(message, data) { this.log('debug', message, data); }
  info(message, data) { this.log('info', message, data); }
  warn(message, data) { this.log('warn', message, data); }
  error(message, data) { this.log('error', message, data); }

  sendToLoggingService(level, message, data) {
    // Sentry, LogRocket 등 외부 서비스 연동
    // 실제 구현은 사용하는 서비스에 따라 다름
  }
}

const logger = new Logger(config.LOG_LEVEL);
```

---

## 🎉 완성된 통합 예시

### **🚀 완전한 React 컴포넌트**
```jsx
import React, { useState, useCallback } from 'react';
import { RecommendationAPI, RecommendationRequestBuilder, PerformanceMonitor } from './utils';

const RecommendationApp = () => {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const api = new RecommendationAPI();
  const monitor = new PerformanceMonitor();

  const handleRecommend = useCallback(async (formData) => {
    setLoading(true);
    setError(null);

    try {
      const request = new RecommendationRequestBuilder()
        .withIntents(formData.intents)
        .withProfile(formData.profile)
        .withMedications(formData.medications)
        .withTopN(formData.topN || 5)
        .build();

      const response = await monitor.measureAPICall(
        () => api.getRecommendations(request),
        '화장품 추천'
      );

      setRecommendations(response.recommendations);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="recommendation-app">
      <RecommendationForm onSubmit={handleRecommend} />
      
      {loading && <LoadingSpinner />}
      {error && <ErrorMessage message={error} />}
      {recommendations.length > 0 && (
        <RecommendationResults recommendations={recommendations} />
      )}
    </div>
  );
};

export default RecommendationApp;
```

---

**🎯 이 가이드로 화장품 추천 API를 완벽하게 통합할 수 있습니다!**

모든 예제 코드는 실제 프로덕션 환경에서 바로 사용 가능하도록 작성되었습니다.