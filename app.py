import streamlit as st
import pandas as pd
import json
import time
import re
import os
import base64
import altair as alt
from utils import get_related_keywords, get_blog_search_result, select_best_keywords_with_ai
from data_loader import (
    load_population_data, get_sido_list, get_sigungu_list, get_dong_list,
    aggregate_population_data, get_persona_from_aggregated
)

# 페이지 설정
st.set_page_config(page_title="Brandiup 키워드 전략 시스템", layout="wide")

# --- 이미지 처리 함수 ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- CSS 디자인 ---
st.markdown("""
<style>
    .report-container { padding: 20px; }
    
    /* [수정] 사이드바 헤더 숨김 제거 -> 버튼 복구됨 */
    
    /* 카드 스타일 */
    .pro-card {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
        color: #333333 !important;
        height: 100%;
    }
    .pro-card h1, .pro-card h2, .pro-card h3, .pro-card h4, .pro-card p, .pro-card div, .pro-card span {
        color: #333333 !important;
    }
    .section-header-container {
        display: flex;
        align-items: center;
        margin-top: 30px;
        margin-bottom: 15px;
        border-bottom: 2px solid #f0f2f6;
        padding-bottom: 10px;
    }
    .section-badge {
        background-color: #1E3A8A;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
        margin-right: 12px;
    }
    .section-title-text {
        font-size: 22px;
        font-weight: 800;
        color: #333;
    }
    .card-header {
        font-size: 14px;
        font-weight: 600;
        color: #666666 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .card-title {
        font-size: 22px; /* 폰트 사이즈 살짝 조정 */
        font-weight: 800;
        color: #1E3A8A !important;
        margin-bottom: 15px;
        min-height: 50px;
        display: flex;
        align-items: center;
    }
    .card-sub-metric { font-size: 14px; color: #555; }
    
    .solution-box {
        background-color: #F0F9FF !important;
        border-left: 5px solid #2563EB;
        padding: 20px;
        border-radius: 4px;
    }
    [data-testid="stBarChart"] {
        background-color: #ffffff;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #eee;
    }
    hr { margin: 20px 0; border-color: #eee; }
    
    /* 사이드바 스타일 */
    .sidebar-logo-img {
        width: 50px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    .sidebar-title {
        text-align: center;
        font-weight: 700;
        font-size: 16px;
        color: #FFFFFF !important; /* 흰색 글씨 */
        text-shadow: 0px 1px 3px rgba(0,0,0,0.3);
        line-height: 1.3;
        margin-bottom: 20px;
    }
    
    /* 대기 화면 로고 */
    .splash-logo {
        width: 180px;
        border-radius: 30px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        transition: transform 0.3s;
    }
    .splash-logo:hover { transform: scale(1.02); }
    .main-title-logo {
        width: 45px;
        height: 45px;
        border-radius: 10px;
        margin-right: 15px;
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

# --- 메인 앱 ---

if 'pop_df' not in st.session_state:
    with st.spinner("데이터 베이스 로딩 중..."):
        st.session_state['pop_df'] = load_population_data()

df = st.session_state['pop_df']

# --- 사이드바 ---
with st.sidebar:
    # 로고 영역
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        # 상단 여백을 조금 주고 로고 배치
        st.markdown(f"""
            <div style="text-align: center; margin-top: 10px;">
                <img src="data:image/png;base64,{img_b64}" class="sidebar-logo-img">
                <div class="sidebar-title">
                    키워드 전략<br>분석시스템
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<h2 style='text-align: center;'>BrandiUp</h2>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
    
    st.header("정보 입력")
    
    shop_name = st.text_input("가게명", "명가 닭국수")
    products = st.text_input("주력 상품 (콤마로 구분)", "닭국수, 얼큰칼국수, 만두")
    
    st.markdown("---")
    st.markdown("**📍 분석 지역 선택**")
    
    sido_list = get_sido_list(df)
    default_sido_index = 0
    if "경기도" in sido_list: default_sido_index = sido_list.index("경기도")
    selected_sido = st.selectbox("시/도", sido_list, index=default_sido_index)
    
    sigungu_list = get_sigungu_list(df, selected_sido)
    default_sigungu_index = 0
    if "용인시 처인구" in sigungu_list: default_sigungu_index = sigungu_list.index("용인시 처인구")
    selected_sigungu = st.selectbox("시/군/구", sigungu_list, index=default_sigungu_index)
    
    dong_list = get_dong_list(df, selected_sido, selected_sigungu)
    selected_dongs = st.multiselect("읍/면/동 (다중 선택 가능)", dong_list)
    
    st.markdown("---")
    run_btn = st.button("분석 리포트 생성 🚀", type="primary", use_container_width=True)

# --- 메인 로직 ---
if run_btn:
    # 로고 타이틀
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{img_b64}" class="main-title-logo">
            <h1 style="margin: 0; padding: 0; font-size: 2.5rem;">Brandiup 상권 분석 리포트</h1>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("📊 Brandiup 상권 분석 리포트")
    
    if not selected_dongs:
        st.error("⚠️ 분석할 읍/면/동을 최소 1개 이상 선택해주세요.")
    else:
        agg_data = aggregate_population_data(df, selected_sido, selected_sigungu, selected_dongs)
        persona = get_persona_from_aggregated(agg_data)
        
        location_str = f"{selected_sido} {selected_sigungu} {selected_dongs[0]}"
        if len(selected_dongs) > 1:
            location_str += f" 외 {len(selected_dongs)-1}곳"

        # 섹션 1: 인구 분석
        st.markdown(f"""
        <div class="section-header-container">
            <span class="section-badge">01</span>
            <span class="section-title-text">우리 동네 인구 분석 : {location_str}</span>
        </div>
        """, unsafe_allow_html=True)
        
        col_demo_1, col_demo_2 = st.columns([1, 2])
        
        with col_demo_1:
            st.markdown(f"""
            <div class='pro-card'>
                <div class='card-header'>핵심 고객 (Core Target)</div>
                <div class='card-title' style='font-size: 28px;'>{persona}</div>
                <hr style='margin: 15px 0; border-color: #eee;'>
                <div class='card-sub-metric'>
                    선택하신 <b>{len(selected_dongs)}개 지역</b>의 거주 인구를 합산하여<br>
                    도출된 <b>주요 고객층</b>입니다.
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_demo_2:
            if agg_data:
                chart_df = pd.DataFrame.from_dict(agg_data, orient='index').reset_index()
                chart_df.columns = ['연령대', '남성', '여성']
                chart_long = pd.melt(chart_df, id_vars=['연령대'], var_name='성별', value_name='인구수')
                
                c = alt.Chart(chart_long).mark_bar().encode(
                    x=alt.X('연령대', axis=alt.Axis(labelAngle=0, title=None)),
                    y=alt.Y('인구수', axis=alt.Axis(title=None)),
                    color=alt.Color('성별', scale=alt.Scale(domain=['남성', '여성'], range=['#4285F4', '#FF5252'])),
                    tooltip=['연령대', '성별', '인구수']
                ).properties(height=300)
                st.altair_chart(c, use_container_width=True)

        # 섹션 2: AI 전략
        st.markdown(f"""
        <div class="section-header-container">
            <span class="section-badge">02</span>
            <span class="section-title-text">맞춤형 키워드 전략</span>
        </div>
        """, unsafe_allow_html=True)
        
        with st.spinner(f"'{products}' 관련 네이버 검색 데이터를 분석 중입니다..."):
            # 1. API로 씨앗 키워드 조회
            seed_list = [f"{selected_sigungu} 맛집"] 
            main_product = products.split(",")[0].strip()
            seed_list.append(f"{selected_sigungu} {main_product}")
            
            validated_keywords = get_related_keywords(seed_list)
            
        # 2. AI로 선별 (티어별 분류 후 선택)
        if validated_keywords:
            with st.spinner("데이터 기반 최적의 전략을 수립 중입니다..."):
                ai_result = select_best_keywords_with_ai(shop_name, location_str, products, persona, validated_keywords)
                
                if ai_result:
                    try:
                        ai_data = json.loads(ai_result)
                        
                        c1, c2, c3 = st.columns(3)
                        
                        # 1단계 (Volume)
                        kwd1_data = ai_data.get("1단계_선정", {})
                        kwd1_doc = get_blog_search_result(kwd1_data.get("keyword", ""))['total']
                        
                        with c1:
                            st.markdown(f"""
                            <div class='pro-card'>
                                <div class='card-header'>STEP 1. 가게 알리기 (노출)</div>
                                <div class='card-title'>{kwd1_data.get('keyword', '-')}</div>
                                <div>월간 검색량 <span style='font-weight:bold;'>{kwd1_data.get('volume', 0):,}</span>건</div>
                                <div>블로그 문서 <span style='font-weight:bold;'>{kwd1_doc:,}</span>개</div>
                                <hr style='margin: 15px 0; border-color: #eee;'>
                                <div class='card-sub-metric'>
                                    {kwd1_data.get('reason', '가장 많은 사람이 검색하는 키워드입니다.')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # 2단계 (Targeting)
                        kwd2_data = ai_data.get("2단계_선정", {})
                        kwd2_doc = get_blog_search_result(kwd2_data.get("keyword", ""))['total']
                        
                        with c2:
                            st.markdown(f"""
                            <div class='pro-card'>
                                <div class='card-header'>STEP 2. 손님 뺏어오기 (유입)</div>
                                <div class='card-title'>{kwd2_data.get('keyword', '-')}</div>
                                <div>월간 검색량 <span style='font-weight:bold;'>{kwd2_data.get('volume', 0):,}</span>건</div>
                                <div>블로그 문서 <span style='font-weight:bold;'>{kwd2_doc:,}</span>개</div>
                                <hr style='margin: 15px 0; border-color: #eee;'>
                                <div class='card-sub-metric'>
                                    {kwd2_data.get('reason', '유사 메뉴를 찾는 고객을 유인합니다.')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # 3단계 (Niche)
                        kwd3_data = ai_data.get("3단계_선정", {})
                        kwd3_doc = get_blog_search_result(kwd3_data.get("keyword", ""))['total']
                        
                        with c3:
                            st.markdown(f"""
                            <div class='pro-card' style='border: 2px solid #2563EB;'>
                                <div class='card-header' style='color:#2563EB !important;'>STEP 3. 단골 만들기 (핵심)</div>
                                <div class='card-title' style='color:#D32F2F !important;'>{kwd3_data.get('keyword', '-')}</div>
                                <div>월간 검색량 <span style='font-weight:bold;'>{kwd3_data.get('volume', 0):,}</span>건</div>
                                <div>블로그 문서 <span style='font-weight:bold;'>{kwd3_doc:,}</span>개</div>
                                <hr style='margin: 15px 0; border-color: #eee;'>
                                <div class='card-sub-metric'>
                                    {kwd3_data.get('reason', '경쟁은 적고 실구매율이 높은 알짜배기입니다.')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class='pro-card solution-box' style='margin-top: 20px;'>
                            <h3 style='color:#1E3A8A !important;'>💡 Brandiup 솔루션 제안</h3>
                            <p>
                                사장님, 실제 검색 데이터를 기반으로 도출된 <b>최적의 3-Track 전략</b>입니다.<br><br>
                                1. <b>'{kwd1_data.get('keyword')}'</b>: 지역 내 브랜드 인지도 확보 (검색량 최우선)<br>
                                2. <b>'{kwd2_data.get('keyword')}'</b>: 경쟁 업체/메뉴 수요 흡수 (연관성)<br>
                                3. <b>'{kwd3_data.get('keyword')}'</b>: 확실한 상위 노출 및 구매 전환 (효율성)
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # 섹션 3
                        st.markdown(f"""
                        <div class="section-header-container">
                            <span class="section-badge">03</span>
                            <span class="section-title-text">경쟁 가게 분석</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        target_kwd = kwd3_data.get('keyword')
                        st.caption(f"'{target_kwd}' 검색 시 1페이지에 노출되는 경쟁사 콘텐츠입니다.")
                        
                        top_posts = get_blog_search_result(target_kwd)['items']

                        if top_posts:
                            cols = st.columns(3)
                            for idx, post in enumerate(top_posts):
                                with cols[idx]:
                                    st.markdown(f"""
                                    <div class='pro-card' style='padding:15px; min-height:200px;'>
                                        <div class='card-header'>TOP {idx+1}</div>
                                        <div style='font-weight:bold; margin-bottom:10px; font-size:14px;'>
                                            {clean_html(post['title'])}
                                        </div>
                                        <div style='font-size:12px; color:#666;'>
                                            {clean_html(post['description'])[:60]}...
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.info("상위 노출된 강력한 경쟁 콘텐츠가 없습니다. (무주공산)")

                        # 섹션 4
                        st.markdown(f"""
                        <div class="section-header-container">
                            <span class="section-badge">04</span>
                            <span class="section-title-text">블로그 제목 추천</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption("손님이 클릭하고 싶게 만드는 매력적인 제목 3선입니다.")
                        
                        for t in ai_data.get("추천_제목", []):
                            st.success(f"✅ {t}")
                    
                    except Exception as e:
                        st.error(f"데이터 처리 중 오류: {e}")
                else:
                    st.error("AI 분석 실패")
        else:
            st.warning("네이버 검색 데이터가 부족하여 분석할 수 없습니다. (키워드가 너무 희귀할 수 있습니다)")

else:
    # 대기 화면
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(f"""
        <div style="
            display: flex;
            justify-content: center;
            align-items: center;
            height: 70vh;
            flex-direction: column;
        ">
            <img class="splash-logo" src="data:image/png;base64,{img_b64}">
        </div>
        """, unsafe_allow_html=True)