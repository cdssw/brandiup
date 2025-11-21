import streamlit as st
import pandas as pd
import json
import time
import re
import os
import base64
import logging
import altair as alt
from utils import extract_keyword_materials, generate_and_validate_keywords, get_blog_search_result
from data_loader import (
    load_population_data, get_sido_list, get_sigungu_list, get_dong_list,
    aggregate_population_data, get_persona_from_aggregated
)

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Brandiup 키워드 전략 시스템", layout="wide")

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- CSS 디자인 (브랜디업 #153d63 적용) ---
st.markdown("""
<style>
    /* 기본 설정 */
    .report-container { padding: 20px; }
    [data-testid="stSidebarHeader"] { display: none; }
    section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
    [data-testid="InputInstructions"] { display: none !important; }

    /* 버튼 */
    div.stButton > button {
        background-color: #153d63 !important; color: white !important; border: none !important; width: 100%;
    }
    div.stButton > button:hover { background-color: #102a44 !important; color: white !important; }

    /* 인사이트 박스 */
    .insight-box {
        background-color: #F0F4F8;
        border-left: 5px solid #153d63;
        padding: 20px;
        border-radius: 8px;
        color: #333;
        margin-bottom: 25px;
        font-size: 16px;
        line-height: 1.6;
    }

    /* 섹션 헤더 */
    .section-header-container {
        display: flex;
        align-items: center;
        margin-top: 30px;
        margin-bottom: 15px;
        border-bottom: 2px solid #f0f2f6;
        padding-bottom: 10px;
    }
    .section-badge {
        background-color: #153d63;
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

    /* 카드 스타일 */
    .pro-card {
        background-color: #ffffff !important;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
        height: 100%;
        color: #333;
    }
    .card-header { font-size: 13px; font-weight: 700; color: #666; margin-bottom: 8px; }
    .card-title { font-size: 24px; font-weight: 800; color: #153d63 !important; margin-bottom: 10px; }
    .card-sub-metric { font-size: 14px; color: #555; line-height: 1.4; }
    .total-pop { font-size: 18px; font-weight: bold; color: #333; margin-top: 5px; }

    /* 키워드 리스트 스타일 */
    .keyword-item {
        background-color: white;
        border: 1px solid #ddd;
        padding: 12px 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: box-shadow 0.2s;
    }
    .keyword-item:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-color: #153d63;
    }
    .kwd-text { font-weight: 700; color: #333; font-size: 16px; }
    .kwd-vol { font-size: 14px; color: #666; }
    .kwd-tag {
        font-size: 12px; padding: 3px 8px; border-radius: 12px; font-weight: bold; margin-left: 10px;
    }
    .tag-main { background-color: #E3F2FD; color: #1565C0; }
    .tag-niche { background-color: #E8F5E9; color: #2E7D32; }

    /* 아이디어 박스 */
    .idea-card {
        background-color: #fff;
        border: 1px solid #eee;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    
    /* 네이버 링크 */
    a.naver-link {
        text-decoration: none; color: #03C75A; font-weight: bold; font-size: 14px; margin-left: 10px;
    }
    
    /* 사이드바 */
    .sidebar-logo-img { width: 50px; border-radius: 12px; margin-bottom: 5px; }
    .sidebar-title { text-align: center; font-weight: 800; font-size: 16px; color: #153d63 !important; margin: 0 0 20px 0; line-height: 1.3; }
    .splash-logo { width: 120px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); opacity: 0.9; }
    .main-title-logo { width: 45px; height: 45px; border-radius: 10px; margin-right: 15px; vertical-align: middle; }
    
    /* 차트 배경 */
    [data-testid="stBarChart"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# --- 데이터 로드 ---
if 'pop_df' not in st.session_state:
    st.session_state['pop_df'] = load_population_data()
df = st.session_state['pop_df']

# --- 사이드바 ---
with st.sidebar:
    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(f"""<div style="text-align:center; margin-bottom:10px;"><img src="data:image/png;base64,{img_b64}" class="sidebar-logo-img"><div class="sidebar-title">키워드 전략<br>분석시스템</div></div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.header("정보 입력")
    shop_name = st.text_input("가게명", "명가 닭국수")
    category = st.selectbox("업종 카테고리", ["한식", "중식", "일식", "양식", "카페/디저트", "고기/구이", "술집", "뷰티/미용", "숙박/펜션", "기타"])
    products = st.text_input("대표 메뉴", "닭국수")
    tags_input = st.text_input("가게 특징 태그 (#구분)", "#해장 #비오는날 #든든한점심")
    
    st.markdown("---")
    st.markdown("**📍 분석 지역 선택**")
    sido_list = get_sido_list(df)
    idx_sido = sido_list.index("경기도") if "경기도" in sido_list else 0
    selected_sido = st.selectbox("시/도", sido_list, index=idx_sido)
    sigungu_list = get_sigungu_list(df, selected_sido)
    idx_sigungu = sigungu_list.index("용인시 처인구") if "용인시 처인구" in sigungu_list else 0
    selected_sigungu = st.selectbox("시/군/구", sigungu_list, index=idx_sigungu)
    dong_list = get_dong_list(df, selected_sido, selected_sigungu)
    selected_dongs = st.multiselect("읍/면/동 (다중 선택)", dong_list, placeholder="분석 지역 선택")
    
    st.markdown("---")
    run_btn = st.button("전략 키워드 리포트 생성 🚀", type="primary")

# --- 메인 로직 ---
if run_btn:
    if not selected_dongs:
        st.error("지역을 선택해주세요.")
    else:
        logo_path = "images/logo.png"
        img_html = ""
        if os.path.exists(logo_path):
            img_b64 = get_base64_of_bin_file(logo_path)
            img_html = f'<img src="data:image/png;base64,{img_b64}" class="main-title-logo">'
        
        st.markdown(f"""<div style="display:flex; align-items:center; margin-bottom:20px;">{img_html}<h1 style="margin:0; padding:0; font-size:2.2rem; color:#153d63;">Brandiup 상권 분석 리포트</h1></div>""", unsafe_allow_html=True)

        # 1. 인구 분석
        agg_data = aggregate_population_data(df, selected_sido, selected_sigungu, selected_dongs)
        persona = get_persona_from_aggregated(agg_data)
        
        # [추가] 총 인구수 계산
        total_population = 0
        if agg_data:
            total_population = sum(sum(v.values()) for v in agg_data.values())

        loc_str = f"{selected_sigungu} {selected_dongs[0]}" + (f" 외 {len(selected_dongs)-1}곳" if len(selected_dongs)>1 else "")
        
        st.markdown(f"""<div class="section-header-container"><span class="section-badge">01</span><span class="section-title-text">우리 동네 인구 분석 : {loc_str}</span></div>""", unsafe_allow_html=True)
        
        col_demo_1, col_demo_2 = st.columns([1, 2])
        with col_demo_1:
            st.markdown(f"""
            <div class='pro-card'>
                <div class='card-header'>CORE TARGET</div>
                <div class='card-title'>{persona}</div>
                <hr style='margin:15px 0; border-color:#eee;'>
                <div class='card-header'>TOTAL POPULATION</div>
                <div class='total-pop'>{total_population:,} 명</div>
                <div class='card-sub-metric' style='margin-top:5px;'>선택하신 상권의 총 거주 인구입니다.</div>
            </div>""", unsafe_allow_html=True)
        
        with col_demo_2:
            if agg_data:
                chart_df = pd.DataFrame.from_dict(agg_data, orient='index').reset_index()
                chart_df.columns = ['연령대', '남성', '여성']
                chart_long = pd.melt(chart_df, id_vars=['연령대'], var_name='성별', value_name='인구수')
                
                # [수정] 차트 디자인 개선 (브랜디업 컬러 + 가로 글씨 + 높이 확대)
                c = alt.Chart(chart_long).mark_bar().encode(
                    x=alt.X('연령대', axis=alt.Axis(labelAngle=0, title=None)), # 가로 글씨
                    y=alt.Y('인구수', axis=alt.Axis(title=None)),
                    color=alt.Color('성별', scale=alt.Scale(domain=['남성', '여성'], range=['#153d63', '#FF8F00'])), # 브랜드 컬러
                    tooltip=['연령대', '성별', '인구수']
                ).properties(height=350) # 높이 확대
                
                st.altair_chart(c, use_container_width=True)

        # 2. 키워드 분석 시작
        st.markdown(f"<div class='section-header-container'><span class='section-badge'>02</span><span class='section-title-text'>전략 키워드 리포트</span></div>", unsafe_allow_html=True)
        
        with st.spinner("AI가 메뉴를 확장하고 키워드 조합을 검증하고 있습니다..."):
            # [Step 1] 재료 추출
            materials = extract_keyword_materials(shop_name, products, category, tags_input, persona, loc_str)
            
            if materials:
                # 인사이트 박스 출력
                insight_text = materials.get('insight', '데이터 분석 기반의 전략 제안입니다.')
                st.markdown(f"""
                <div class="insight-box">
                    💡 <strong>AI Insight:</strong> {insight_text}
                </div>
                """, unsafe_allow_html=True)
                
                # [Step 2] 조합 생성 및 검증
                report = generate_and_validate_keywords(loc_str, products, tags_input, materials)
                
                # 결과 출력 (2단 컬럼)
                col_main, col_detail = st.columns(2)
                
                # A. 메인 타겟 키워드
                with col_main:
                    st.markdown("#### 📢 메인 타겟 키워드 (Volume)")
                    st.caption("검색량이 많아 인지도 상승과 유입에 효과적인 키워드입니다.")
                    
                    if report['main_keywords']:
                        for item in report['main_keywords']:
                            naver_url = f"https://search.naver.com/search.naver?query={item['keyword']}"
                            st.markdown(f"""
                            <div class="keyword-item">
                                <div>
                                    <span class="kwd-text">{item['keyword']}</span>
                                    <span class="kwd-tag tag-main">Main</span>
                                </div>
                                <div>
                                    <span class="kwd-vol">월 {item['volume']:,}건</span>
                                    <a href="{naver_url}" target="_blank" class="naver-link">🔍</a>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("조건에 맞는 메인 키워드가 없습니다.")

                # B. 세부 공략 키워드
                with col_detail:
                    st.markdown("#### 🎯 세부 공략 키워드 (Conversion)")
                    st.caption("구체적인 상황/니즈가 반영되어 구매 전환율이 높은 꿀통입니다.")
                    
                    if report['detail_keywords']:
                        for item in report['detail_keywords']:
                            naver_url = f"https://search.naver.com/search.naver?query={item['keyword']}"
                            st.markdown(f"""
                            <div class="keyword-item">
                                <div>
                                    <span class="kwd-text">{item['keyword']}</span>
                                    <span class="kwd-tag tag-niche">Niche</span>
                                </div>
                                <div>
                                    <span class="kwd-vol">월 {item['volume']:,}건</span>
                                    <a href="{naver_url}" target="_blank" class="naver-link">🔍</a>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("조건에 맞는 세부 키워드가 없습니다.")

                # 3. 콘텐츠 아이디어
                st.markdown(f"<div class='section-header-container'><span class='section-badge'>03</span><span class='section-title-text'>콘텐츠 제작 아이디어</span></div>", unsafe_allow_html=True)
                
                cols = st.columns(3)
                for idx, idea in enumerate(report['content_ideas']):
                    with cols[idx]:
                        st.markdown(f"""
                        <div class="idea-card">
                            <h5 style="margin:0 0 10px 0; color:#153d63;">📝 아이디어 {idx+1}</h5>
                            <div style="font-size:14px; color:#555;">{idea}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.error("AI 분석에 실패했습니다.")

else:
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(f"""<div style="display:flex; justify-content:center; align-items:center; height:70vh;"><img src="data:image/png;base64,{img_b64}" class="splash-logo"></div>""", unsafe_allow_html=True)