import streamlit as st
import pandas as pd
import time
from utils import get_keyword_volume, get_blog_count

st.set_page_config(page_title="브랜디업 스캐너", layout="wide")

st.title("🕵️‍♀️ 브랜디업 상권 분석기 (MVP)")

with st.sidebar:
    st.header("가게 정보 입력")
    shop_name = st.text_input("가게 이름", "명가 닭국수")
    location = st.text_input("지역 (시/구)", "용인시 처인구")
    category_keyword = st.text_input("대표 업종", "닭국수")
    run_btn = st.button("분석 시작 🚀")

if run_btn:
    st.divider()
    with st.spinner(f"'{shop_name}' 주변 꿀통 키워드를 발굴 중입니다..."):
        
        # 1. 키워드 확장
        target_keyword = f"{location} {category_keyword}"
        raw_data = get_keyword_volume(target_keyword)
        
        # [추가] 데이터 개수 확인용
        st.write(f"API가 찾아낸 연관 키워드 개수: {len(raw_data)} 개") 

        if not raw_data:
            st.error("데이터를 가져오지 못했습니다. API 키 설정을 확인하세요.")
        else:
            # 2. 1차 필터링 (검색량 적절한 것만)
            candidates = []
            for item in raw_data:
                kwd = item['relKeyword']
                # PC/Mobile 검색량 합산 (문자열 '< 10' 처리)
                pc = int(item['monthlyPcQcCnt']) if isinstance(item['monthlyPcQcCnt'], int) else 0
                mo = int(item['monthlyMobileQcCnt']) if isinstance(item['monthlyMobileQcCnt'], int) else 0
                total = pc + mo
                
                if 300 <= total <= 30000: # 너무 적거나 많은 것 제외
                    candidates.append({"키워드": kwd, "검색량": total})
            
            # 3. 상위 20개만 추출하여 블로그 경쟁률 분석
            df = pd.DataFrame(candidates)
            if not df.empty:
                df = df.sort_values(by="검색량", ascending=False).head(20)
                
                doc_counts = []
                ratios = []
                
                progress_bar = st.progress(0)
                
                for idx, row in df.iterrows():
                    # 블로그 문서수 조회
                    count = get_blog_count(row['키워드'])
                    doc_counts.append(count)
                    
                    # 효율지수 (검색량 / 문서수) * 100
                    ratio = round((row['검색량'] / (count + 1)) * 100, 2)
                    ratios.append(ratio)
                    
                    # [중요] API 속도 제한 방지 (0.1초 대기)
                    time.sleep(0.1)
                    
                    # 진행률 업데이트
                    current_idx = list(df.index).index(idx)
                    progress_bar.progress((current_idx + 1) / len(df))
                
                df['문서수'] = doc_counts
                df['꿀통지수'] = ratios
                
                # 꿀통지수 높은 순 정렬
                df_final = df.sort_values(by="꿀통지수", ascending=False)
                
                # 결과 출력
                best = df_final.iloc[0]
                st.success(f"발굴 성공! '{category_keyword}' 대신 **'{best['키워드']}'** 키워드를 잡아야 합니다!")
                st.metric(label="추천 키워드", value=best['키워드'], delta=f"효율 {best['꿀통지수']}점")
                
                st.subheader("📋 상세 분석 리스트")
                st.dataframe(df_final, use_container_width=True)
            else:
                st.warning("적절한 키워드를 찾지 못했습니다.")