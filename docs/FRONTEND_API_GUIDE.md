# 🎨 프론트엔드 & 기획자를 위한 화장품 추천 API 가이드

## 📋 목차
1. [화면별 필요한 사용자 입력 데이터](#화면별-필요한-사용자-입력-데이터)
2. [API 요청 방법](#api-요청-방법)
3. [화면 설계 가이드](#화면-설계-가이드)
4. [실제 구현 예시](#실제-구현-예시)
5. [에러 처리 가이드](#에러-처리-가이드)

---

## 🎯 화면별 필요한 사용자 입력 데이터

### **1️⃣ 기본 추천 화면 (필수)**

#### **🔥 반드시 받아야 하는 데이터**
```
✅ 사용자 의도 (필수)
- 보습이 필요해요
- 주름 개선하고 싶어요  
- 여드름 케어하고 싶어요
- 피부 톤업하고 싶어요
```

#### **📱 화면 구성 예시**
```
┌─────────────────────────────────┐
│ 어떤 고민이 있으신가요? (복수선택)    │
├─────────────────────────────────┤
│ ☐ 건조함/보습 필요               │
│ ☐ 주름/노화 개선                │
│ ☐ 여드름/트러블 케어             │
│ ☐ 피부 톤업/미백                │
│ ☐ 민감성 피부 케어              │
│ ☐ 모공 케어                    │
└─────────────────────────────────┘
```

#### **🔗 API 매핑**
```javascript
// 사용자 선택 → API 파라미터
const userSelections = {
  "건조함/보습 필요": "moisturizing",
  "주름/노화 개선": "anti-aging", 
  "여드름/트러블 케어": "acne-care",
  "피부 톤업/미백": "brightening",
  "민감성 피부 케어": "sensitive-care",
  "모공 케어": "pore-care"
}
```

---

### **2️⃣ 상세 프로필 화면 (선택사항)**

#### **👤 사용자 기본 정보**
```
📝 연령대 (선택)
○ 10대  ○ 20대  ○ 30대  ○ 40대  ○ 50대  ○ 60대+

👫 성별 (선택)  
○ 남성  ○ 여성  ○ 기타

🧴 피부 타입 (선택)
○ 건성  ○ 지성  ○ 복합성  ○ 민감성  ○ 정상
```

#### **🚨 알레르기 정보 (선택)**
```
┌─────────────────────────────────┐
│ 알레르기가 있는 성분이 있나요?      │
├─────────────────────────────────┤
│ ☐ 향료 (fragrance)             │
│ ☐ 알코올 (alcohol)             │
│ ☐ 파라벤 (paraben)             │
│ ☐ 기타: [직접입력]              │
└─────────────────────────────────┘
```

---

### **3️⃣ 의약품 정보 화면 (선택사항)**

#### **💊 복용 중인 약물**
```
┌─────────────────────────────────┐
│ 현재 복용 중인 약물이 있나요?       │
├─────────────────────────────────┤
│ ☐ 레티놀 제품 사용 중            │
│ ☐ 여드름 치료제 복용 중          │
│ ☐ 혈압약 복용 중                │
│ ☐ 임신/수유 중                  │
│ ☐ 기타: [약물명 직접입력]        │
└─────────────────────────────────┘
```

---

### **4️⃣ 추가 옵션 화면 (선택사항)**

#### **💰 가격대**
```
💰 예산 범위
├ 2만원 이하
├ 2-5만원  
├ 5-10만원
└ 10만원 이상
```

#### **🏷️ 브랜드/카테고리 선호도**
```
🏷️ 선호 브랜드 (선택)
☐ 이니스프리  ☐ 라운드랩  ☐ 스킨1004  ☐ 토리든

📦 원하는 제품 타입 (선택)  
☐ 크림  ☐ 세럼  ☐ 에센스  ☐ 토너
```

---

## 🔌 API 요청 방법

### **📍 기본 정보**
```
🌐 서버 주소: http://localhost:8000
📡 엔드포인트: POST /api/v1/recommend
📋 Content-Type: application/json
```

### **🎯 단계별 API 요청**

#### **1단계: 최소 요청 (의도만)**
```javascript
// 가장 간단한 요청
const basicRequest = {
  intent_tags: ["moisturizing", "anti-aging"],
  top_n: 5
}

fetch('http://localhost:8000/api/v1/recommend', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(basicRequest)
})
```

#### **2단계: 프로필 포함 요청**
```javascript
// 사용자 프로필 포함
const profileRequest = {
  intent_tags: ["acne-care", "sensitive-care"],
  user_profile: {
    age_group: "20s",
    gender: "female", 
    skin_type: "sensitive",
    skin_concerns: ["acne", "redness"],
    allergies: ["fragrance"]
  },
  top_n: 5
}
```

#### **3단계: 풀옵션 요청**
```javascript
// 모든 정보 포함
const fullRequest = {
  intent_tags: ["moisturizing", "anti-aging"],
  user_profile: {
    age_group: "30s",
    gender: "female",
    skin_type: "dry",
    skin_concerns: ["wrinkles", "dryness"],
    allergies: ["alcohol"]
  },
  medications: [
    {
      name: "레티놀 크림",
      active_ingredients: ["retinol"]
    }
  ],
  usage_context: {
    season: "winter",
    time_of_day: "night"
  },
  price_range: {
    min: 20000,
    max: 80000
  },
  categories: ["크림", "세럼"],
  brands: ["이니스프리", "라운드랩"],
  top_n: 10
}
```

---

## 🎨 화면 설계 가이드

### **📱 추천 플로우 설계**

#### **Step 1: 의도 선택 화면**
```
┌─────────────────────────────────┐
│        어떤 고민이 있으신가요?      │
│                                 │
│  🧴 건조함, 보습이 필요해요       │
│  ✨ 주름, 노화가 걱정돼요         │
│  🔴 여드름, 트러블이 있어요       │
│  💡 피부 톤업하고 싶어요          │
│  🌿 민감성 피부예요              │
│  🕳️ 모공이 신경 쓰여요           │
│                                 │
│           [다음 단계] ➡️          │
└─────────────────────────────────┘
```

#### **Step 2: 간단 프로필 (선택)**
```
┌─────────────────────────────────┐
│      더 정확한 추천을 위해...      │
│                                 │
│  👤 연령대: [20대 ▼]            │
│  🧴 피부타입: [건성 ▼]          │
│                                 │
│  ⚠️ 알레르기 성분이 있나요?       │
│     ☐ 향료  ☐ 알코올  ☐ 파라벤  │
│                                 │
│  [건너뛰기]    [추천받기] ➡️      │
└─────────────────────────────────┘
```

#### **Step 3: 추천 결과 화면**
```
┌─────────────────────────────────┐
│         맞춤 추천 결과 ✨         │
├─────────────────────────────────┤
│ 1️⃣ 히알루론산 수분 세럼          │
│    💯 점수: 92점                │
│    💡 추천 이유:                │
│    • 보습 효과가 뛰어남          │
│    • 20대 건성 피부에 최적       │
│    • 안전성 검증 완료            │
│    💰 가격: 35,000원            │
├─────────────────────────────────┤
│ 2️⃣ 콜라겐 탄력 크림             │
│    💯 점수: 89점                │
│    💡 추천 이유:                │
│    • 안티에이징 효과 우수        │
│    • 콜라겐 성분으로 탄력 개선    │
│    💰 가격: 45,000원            │
└─────────────────────────────────┘
```

---

## 💻 실제 구현 예시

### **🔥 React 컴포넌트 예시**

#### **1. 의도 선택 컴포넌트**
```jsx
import React, { useState } from 'react';

const IntentSelector = ({ onNext }) => {
  const [selectedIntents, setSelectedIntents] = useState([]);
  
  const intentOptions = [
    { id: 'moisturizing', label: '🧴 건조함, 보습이 필요해요', icon: '💧' },
    { id: 'anti-aging', label: '✨ 주름, 노화가 걱정돼요', icon: '⏰' },
    { id: 'acne-care', label: '🔴 여드름, 트러블이 있어요', icon: '🎯' },
    { id: 'brightening', label: '💡 피부 톤업하고 싶어요', icon: '✨' },
    { id: 'sensitive-care', label: '🌿 민감성 피부예요', icon: '🌱' },
    { id: 'pore-care', label: '🕳️ 모공이 신경 쓰여요', icon: '🔍' }
  ];

  const handleIntentToggle = (intentId) => {
    setSelectedIntents(prev => 
      prev.includes(intentId) 
        ? prev.filter(id => id !== intentId)
        : [...prev, intentId]
    );
  };

  return (
    <div className="intent-selector">
      <h2>어떤 고민이 있으신가요?</h2>
      <p>여러 개 선택 가능해요</p>
      
      {intentOptions.map(option => (
        <button
          key={option.id}
          className={`intent-option ${selectedIntents.includes(option.id) ? 'selected' : ''}`}
          onClick={() => handleIntentToggle(option.id)}
        >
          <span className="icon">{option.icon}</span>
          <span className="label">{option.label}</span>
        </button>
      ))}
      
      <button 
        className="next-button"
        disabled={selectedIntents.length === 0}
        onClick={() => onNext(selectedIntents)}
      >
        다음 단계 ➡️
      </button>
    </div>
  );
};
```

#### **2. API 호출 함수**
```javascript
// API 호출 유틸리티
const recommendationAPI = {
  // 기본 추천 요청
  async getBasicRecommendations(intentTags, topN = 5) {
    const response = await fetch('http://localhost:8000/api/v1/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent_tags: intentTags,
        top_n: topN
      })
    });
    
    if (!response.ok) {
      throw new Error(`API 오류: ${response.status}`);
    }
    
    return await response.json();
  },

  // 상세 추천 요청  
  async getDetailedRecommendations(requestData) {
    const response = await fetch('http://localhost:8000/api/v1/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestData)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error?.message || '추천 요청 실패');
    }
    
    return await response.json();
  },

  // 지원 태그 목록 조회
  async getSupportedIntentTags() {
    const response = await fetch('http://localhost:8000/api/v1/recommend/intent-tags');
    return await response.json();
  },

  // 지원 카테고리 목록 조회
  async getSupportedCategories() {
    const response = await fetch('http://localhost:8000/api/v1/recommend/categories');
    return await response.json();
  }
};
```

#### **3. 추천 결과 컴포넌트**
```jsx
const RecommendationResults = ({ recommendations, executionSummary }) => {
  return (
    <div className="recommendation-results">
      <div className="header">
        <h2>✨ 맞춤 추천 결과</h2>
        <p>총 {recommendations.length}개 제품을 찾았어요</p>
        <small>응답시간: {(executionSummary.execution_time_seconds * 1000).toFixed(0)}ms</small>
      </div>
      
      {recommendations.map((item, index) => (
        <div key={item.product_id} className="recommendation-item">
          <div className="rank">#{item.rank}</div>
          
          <div className="product-info">
            <h3>{item.product_name}</h3>
            <p className="brand">{item.brand_name}</p>
            <p className="category">{item.category}</p>
          </div>
          
          <div className="scores">
            <div className="final-score">
              💯 {item.final_score.toFixed(1)}점
            </div>
            <div className="intent-score">
              🎯 의도일치: {item.intent_match_score.toFixed(1)}점
            </div>
          </div>
          
          <div className="reasons">
            <h4>💡 추천 이유:</h4>
            <ul>
              {item.reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
          
          {item.warnings.length > 0 && (
            <div className="warnings">
              <h4>⚠️ 주의사항:</h4>
              <ul>
                {item.warnings.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
```

---

## ⚠️ 에러 처리 가이드

### **🚨 주요 에러 케이스**

#### **1. 입력 검증 오류 (400)**
```javascript
// 에러 응답 예시
{
  "error": {
    "code": "VALIDATION_ERROR", 
    "message": "지원하지 않는 의도 태그: ['invalid_tag']"
  },
  "timestamp": "2025-10-28T12:17:22Z",
  "path": "/api/v1/recommend"
}

// 처리 방법
try {
  const result = await recommendationAPI.getBasicRecommendations(intentTags);
} catch (error) {
  if (error.message.includes('지원하지 않는 의도 태그')) {
    alert('선택하신 옵션에 문제가 있어요. 다시 선택해주세요.');
  }
}
```

#### **2. 서버 오류 (500)**
```javascript
// 서버 오류 처리
try {
  const result = await recommendationAPI.getBasicRecommendations(intentTags);
} catch (error) {
  console.error('API 오류:', error);
  alert('잠시 후 다시 시도해주세요.');
}
```

### **🛡️ 안전한 에러 처리 패턴**
```javascript
const safeAPICall = async (apiFunction, fallbackMessage = '오류가 발생했습니다') => {
  try {
    return await apiFunction();
  } catch (error) {
    console.error('API 호출 실패:', error);
    
    // 사용자 친화적 메시지 표시
    if (error.message.includes('의도 태그')) {
      return { error: '선택 옵션을 다시 확인해주세요' };
    } else if (error.message.includes('네트워크')) {
      return { error: '인터넷 연결을 확인해주세요' };
    } else {
      return { error: fallbackMessage };
    }
  }
};
```

---

## 📋 체크리스트

### **🎨 기획자용 체크리스트**
- [ ] 의도 선택 화면 설계 (필수)
- [ ] 사용자 프로필 입력 화면 (선택)
- [ ] 의약품/알레르기 정보 화면 (선택)
- [ ] 추천 결과 표시 화면
- [ ] 에러 상황 처리 화면
- [ ] 로딩 상태 표시

### **💻 개발자용 체크리스트**
- [ ] 의도 태그 매핑 구현
- [ ] API 호출 함수 작성
- [ ] 에러 처리 로직 구현
- [ ] 로딩 상태 관리
- [ ] 응답 데이터 파싱
- [ ] 사용자 입력 검증

---

## 🎯 핵심 포인트

1. **필수는 의도 선택만**: 나머지는 모두 선택사항으로 설계
2. **단계적 접근**: 기본 → 상세 → 결과 순서로 플로우 구성
3. **사용자 친화적**: 전문 용어 대신 쉬운 표현 사용
4. **에러 처리**: 모든 API 호출에 적절한 에러 처리 구현
5. **성능 고려**: 평균 50-250ms 응답시간 활용

**🚀 이 가이드로 사용자 친화적이고 안정적인 추천 서비스를 구축할 수 있습니다!**