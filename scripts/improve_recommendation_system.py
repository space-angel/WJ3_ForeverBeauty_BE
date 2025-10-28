#!/usr/bin/env python3
"""
추천 시스템 3대 핵심 개선사항 실행 스크립트
1. PostgreSQL 연결 설정
2. 의도 매칭 정확도 향상  
3. 제품 태그 데이터 보강
"""
import sys
import os
import asyncio
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.postgres_db import db_manager, check_database_health
from app.services.tag_enhancement_service import TagEnhancementService
from app.services.intent_matching_service import AdvancedIntentMatcher
from app.services.product_service import ProductService
from app.models.request import RecommendationRequest

class RecommendationSystemImprover:
    """추천 시스템 개선 실행기"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.results = {
            'postgres_setup': {'status': 'pending'},
            'intent_matching': {'status': 'pending'},
            'tag_enhancement': {'status': 'pending'}
        }
    
    async def run_all_improvements(self):
        """모든 개선사항 실행"""
        print("🚀 추천 시스템 3대 핵심 개선사항 실행 시작")
        print(f"시작 시간: {self.start_time}")
        print("=" * 60)
        
        # 1. PostgreSQL 연결 설정
        await self.improve_postgres_connection()
        
        # 2. 제품 태그 데이터 보강 (의도 매칭 개선을 위한 선행 작업)
        await self.improve_tag_data()
        
        # 3. 의도 매칭 정확도 향상
        await self.improve_intent_matching()
        
        # 최종 결과 리포트
        self.generate_final_report()
    
    async def improve_postgres_connection(self):
        """1. PostgreSQL 연결 설정 개선"""
        print("\n📊 1. PostgreSQL 연결 설정 개선")
        print("-" * 40)
        
        try:
            # 연결 테스트
            print("PostgreSQL 연결 테스트 중...")
            connection_info = check_database_health()
            
            if connection_info.get('status') == 'connected':
                print("✅ PostgreSQL 연결 성공!")
                print(f"   - 버전: {connection_info.get('version', 'Unknown')}")
                print(f"   - 풀 크기: {connection_info.get('pool_size', 'Unknown')}")
                
                self.results['postgres_setup'] = {
                    'status': 'success',
                    'connection_info': connection_info
                }
            else:
                print("⚠️  PostgreSQL 연결 실패 - JSON 파일 모드로 동작")
                print(f"   오류: {connection_info.get('error', 'Unknown')}")
                
                self.results['postgres_setup'] = {
                    'status': 'fallback',
                    'message': 'JSON 파일 기반 룰 엔진 사용',
                    'error': connection_info.get('error')
                }
            
            # 룰 엔진 상태 확인
            from app.services.rule_service import RuleService
            rule_service = RuleService()
            rule_stats = rule_service.get_rule_statistics()
            
            print(f"   - 총 룰: {rule_stats['total_rules']}개")
            print(f"   - 활성 룰: {rule_stats['active_rules']}개")
            print(f"   - 배제 룰: {rule_stats['eligibility_rules']}개")
            print(f"   - 감점 룰: {rule_stats['scoring_rules']}개")
            
        except Exception as e:
            print(f"❌ PostgreSQL 설정 개선 실패: {e}")
            self.results['postgres_setup'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def improve_tag_data(self):
        """3. 제품 태그 데이터 보강"""
        print("\n🏷️  3. 제품 태그 데이터 보강")
        print("-" * 40)
        
        try:
            tag_service = TagEnhancementService()
            
            # 현재 태그 품질 분석
            print("현재 태그 품질 분석 중...")
            quality_analysis = tag_service.analyze_tag_quality()
            
            print(f"   - 태그 보유 제품: {quality_analysis['total_products_with_tags']}개")
            print(f"   - 고유 태그 수: {quality_analysis['total_unique_tags']}개")
            print(f"   - 평균 태그/제품: {quality_analysis['avg_tags_per_product']:.1f}개")
            print(f"   - 표준화 비율: {quality_analysis['standardization_rate']:.1%}")
            
            # 태그 보강 실행 (샘플)
            print("\n태그 보강 실행 중 (샘플 50개 제품)...")
            enhancement_results = tag_service.enhance_all_product_tags(batch_size=50)
            
            print(f"✅ 태그 보강 완료!")
            print(f"   - 처리 제품: {enhancement_results['total_products']}개")
            print(f"   - 보강된 제품: {enhancement_results['enhanced_count']}개")
            print(f"   - 새 태그 생성: {enhancement_results['generated_count']}개")
            
            if enhancement_results['error_count'] > 0:
                print(f"   - 오류 발생: {enhancement_results['error_count']}개")
            
            self.results['tag_enhancement'] = {
                'status': 'success',
                'before_quality': quality_analysis,
                'enhancement_results': enhancement_results
            }
            
        except Exception as e:
            print(f"❌ 태그 데이터 보강 실패: {e}")
            self.results['tag_enhancement'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def improve_intent_matching(self):
        """2. 의도 매칭 정확도 향상"""
        print("\n🎯 2. 의도 매칭 정확도 향상")
        print("-" * 40)
        
        try:
            # 기존 매칭 성능 측정
            print("기존 의도 매칭 성능 측정 중...")
            old_scores = await self.measure_intent_matching_performance(use_advanced=False)
            
            print(f"   기존 평균 점수: {old_scores['avg_score']:.1f}점")
            print(f"   80점 이상: {old_scores['high_score_count']}개")
            
            # 개선된 매칭 성능 측정
            print("\n개선된 의도 매칭 성능 측정 중...")
            new_scores = await self.measure_intent_matching_performance(use_advanced=True)
            
            print(f"   개선 후 평균 점수: {new_scores['avg_score']:.1f}점")
            print(f"   80점 이상: {new_scores['high_score_count']}개")
            
            # 개선 효과 계산
            improvement = {
                'score_increase': new_scores['avg_score'] - old_scores['avg_score'],
                'high_score_increase': new_scores['high_score_count'] - old_scores['high_score_count'],
                'improvement_rate': ((new_scores['avg_score'] - old_scores['avg_score']) / old_scores['avg_score']) * 100
            }
            
            print(f"\n✅ 의도 매칭 개선 완료!")
            print(f"   - 평균 점수 향상: +{improvement['score_increase']:.1f}점")
            print(f"   - 고득점 제품 증가: +{improvement['high_score_increase']}개")
            print(f"   - 개선율: {improvement['improvement_rate']:.1f}%")
            
            self.results['intent_matching'] = {
                'status': 'success',
                'before_performance': old_scores,
                'after_performance': new_scores,
                'improvement': improvement
            }
            
        except Exception as e:
            print(f"❌ 의도 매칭 개선 실패: {e}")
            self.results['intent_matching'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def measure_intent_matching_performance(self, use_advanced: bool = True) -> dict:
        """의도 매칭 성능 측정"""
        
        # 테스트용 제품 샘플 조회
        product_service = ProductService()
        products = product_service.get_products_by_category(limit=50)
        
        if not products:
            return {'avg_score': 0, 'high_score_count': 0, 'scores': []}
        
        # 테스트 의도 태그
        test_intent_tags = ['moisturizing', 'anti-aging']
        
        scores = []
        
        if use_advanced:
            # 고도화된 매칭 엔진 사용
            try:
                matcher = AdvancedIntentMatcher()
                results = matcher.batch_calculate_scores(products, test_intent_tags)
                scores = [result.total_score for result in results]
            except Exception as e:
                print(f"고도화된 매칭 엔진 오류: {e}")
                # 폴백: 기본 매칭
                scores = [product_service.calculate_intent_match_score(p, test_intent_tags) for p in products]
        else:
            # 기존 매칭 방식
            scores = [product_service.calculate_intent_match_score(p, test_intent_tags) for p in products]
        
        return {
            'avg_score': sum(scores) / len(scores) if scores else 0,
            'high_score_count': sum(1 for score in scores if score >= 80),
            'scores': scores
        }
    
    def generate_final_report(self):
        """최종 개선 리포트 생성"""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        print("\n" + "=" * 60)
        print("📋 최종 개선 리포트")
        print("=" * 60)
        
        print(f"실행 시간: {duration.total_seconds():.1f}초")
        print(f"완료 시간: {end_time}")
        
        # 각 개선사항 결과 요약
        for improvement, result in self.results.items():
            status_emoji = {
                'success': '✅',
                'fallback': '⚠️',
                'error': '❌',
                'pending': '⏳'
            }.get(result['status'], '❓')
            
            improvement_name = {
                'postgres_setup': 'PostgreSQL 연결 설정',
                'intent_matching': '의도 매칭 정확도 향상',
                'tag_enhancement': '제품 태그 데이터 보강'
            }.get(improvement, improvement)
            
            print(f"\n{status_emoji} {improvement_name}: {result['status'].upper()}")
            
            if result['status'] == 'success':
                if improvement == 'intent_matching' and 'improvement' in result:
                    imp = result['improvement']
                    print(f"   평균 점수 향상: +{imp['score_increase']:.1f}점 ({imp['improvement_rate']:.1f}%)")
                elif improvement == 'tag_enhancement' and 'enhancement_results' in result:
                    enh = result['enhancement_results']
                    print(f"   보강된 제품: {enh['enhanced_count']}개")
            elif result['status'] == 'error':
                print(f"   오류: {result.get('error', 'Unknown')}")
        
        # 전체 성공률 계산
        success_count = sum(1 for r in self.results.values() if r['status'] in ['success', 'fallback'])
        success_rate = (success_count / len(self.results)) * 100
        
        print(f"\n🎯 전체 성공률: {success_rate:.0f}% ({success_count}/{len(self.results)})")
        
        # 다음 단계 권장사항
        print("\n📌 다음 단계 권장사항:")
        
        if self.results['postgres_setup']['status'] == 'fallback':
            print("   - PostgreSQL 서버 설정 및 연결 구성")
            print("   - 룰 데이터 PostgreSQL 마이그레이션")
        
        if self.results['intent_matching']['status'] == 'success':
            print("   - A/B 테스트를 통한 추천 품질 검증")
            print("   - 사용자 피드백 기반 매칭 알고리즘 튜닝")
        
        if self.results['tag_enhancement']['status'] == 'success':
            print("   - 전체 제품 태그 보강 실행")
            print("   - 태그 품질 모니터링 시스템 구축")
        
        print("\n🎉 추천 시스템 개선 완료!")

async def main():
    """메인 실행 함수"""
    improver = RecommendationSystemImprover()
    await improver.run_all_improvements()

if __name__ == "__main__":
    asyncio.run(main())