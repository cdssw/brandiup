import streamlit as st
import pandas as pd
from utils import get_keyword_volume, get_blog_count

# 페이지 설정 (아이패드에 맞게 넓게 쓰기)
st.set_page_config(page_title="브랜디업 스캐너", layout="wide")

st.title("🕵️‍♀️ 브랜디업 상권 분석기")

# 1. 입력 섹션
with st.sidebar:
    st.header("가게 정보 입력")
    shop_name = st.text_input("가게 이름", "명가 닭국수")
    location = st.text_input("지역 (시/구/동)", "용인시 처인구")
    category_keyword = st.text_input("대표 업종 키워드", "닭국수")
    
    if st.button("분석 시작 🚀"):
        st.session_state['run'] = True

# 2. 분석 로직 및 결과 표시
if st.session_state.get('run'):
    st.divider()
    
    # 로딩 표시
    with st.spinner(f"'{shop_name}'을 위한 데이터를 분석 중입니다..."):
        
        # A. 핵심 키워드 확장 (지역 + 키워드)
        target_keyword = f"{location} {category_keyword}" # 예: 용인시 처인구 닭국수
        
        # B. 검색광고 API 호출 (연관 키워드 수집)
        raw_data = get_keyword_volume(target_keyword)
        
        # 데이터 가공
        results = []
        for item in raw_data: # API가 최대 1000개 줌 (너무 많으면 끊어야 함)
            kwd = item['relKeyword']
            pc_vol = item['monthlyPcQcCnt']
            mo_vol = item['monthlyMobileQcCnt']
            
            # '< 10' 문자열 처리
            if isinstance(pc_vol, str): pc_vol = 0
            if isinstance(mo_vol, str): mo_vol = 0
            
            total_vol = pc_vol + mo_vol
            
            # 필터링: 검색량이 너무 적거나(100미만) 너무 많은 것(대형키워드) 제외 등 전략적 선택
            if 300 <= total_vol <= 20000: 
                results.append({
                    "키워드": kwd,
                    "검색량": total_vol
                })
        
        # 상위 10개만 추려서 블로그 문서수 조회 (API 호출 제한 아끼기 위해)
        # 검색량 순으로 정렬 후 상위권 추출 혹은 랜덤하게
        df = pd.DataFrame(results)
        if not df.empty:
            df = df.sort_values(by="검색량", ascending=False).head(20) # 상위 20개만 분석
            
            doc_counts = []
            ratios = []
            
            progress_bar = st.progress(0)
            for idx, row in df.iterrows():
                count = get_blog_count(row['키워드'])
                doc_counts.append(count)
                
                # 경쟁률 계산 (검색량 / 문서수) * 100 -> 높을수록 좋음 (검색은 많은데 글은 적음)
                # 0으로 나누기 방지
                ratio = round((row['검색량'] / (count + 1)) * 100, 2)
                ratios.append(ratio)
                progress_bar.progress((list(df.index).index(idx) + 1) / len(df))
            
            df['문서수'] = doc_counts
            df['효율지수(꿀통)'] = ratios
            
            # 꿀통 순서로 정렬
            df_final = df.sort_values(by="효율지수(꿀통)", ascending=False)

            # C. 결과 화면 출력
            
            # 1) 진단 메시지
            top_keyword = df_final.iloc[0]
            st.subheader(f"📢 진단 결과")
            st.markdown(f"""
            사장님, **'{category_keyword}'** 자체는 검색량이 적을 수 있습니다.
            하지만 분석 결과, **'{top_keyword['키워드']}'** 키워드가 기회입니다!
            """)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("추천 키워드", top_keyword['키워드'])
            col2.metric("월간 검색량", f"{top_keyword['검색량']:,} 건")
            col3.metric("경쟁강도(문서수)", f"{top_keyword['문서수']:,} 개", delta="블루오션")

            # 2) 상세 데이터 테이블
            st.subheader("📊 공략 가능한 꿀통 키워드 리스트")
            st.dataframe(df_final, use_container_width=True)
            
        else:
            st.error("검색 결과가 충분하지 않습니다. 키워드를 변경해보세요.")