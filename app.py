import streamlit as st
import pandas as pd
import json
import time
import os
import base64
import logging
import altair as alt
from datetime import datetime
from utils import extract_keyword_materials, generate_and_validate_keywords, get_blog_search_result, get_current_season
from data_loader import (
    load_population_data, get_sido_list, get_sigungu_list, get_dong_list,
    aggregate_population_data, get_persona_from_aggregated
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Brandiup 키워드 전략 시스템", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_base64_of_bin_file(bin_file):
    """이미지를 base64로 인코딩"""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return ""

# --- CSS 디자인 (강화) ---
st.markdown("""
<style>
    /* 기본 설정 */
    .report-container { padding: 20px; }
    [data-testid="stSidebarHeader"] { display: none; }
    section[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
    [data-testid="InputInstructions"] { display: none !important; }

    /* 버튼 */
    div.stButton > button {
        background: linear-gradient(135deg, #153d63 0%, #1a5280 100%) !important;
        color: white !important;
        border: none !important;
        width: 100%;
        font-weight: 600;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #102a44 0%, #153d63 100%) !important;
        box-shadow: 0 4px 12px rgba(21, 61, 99, 0.3);
        transform: translateY(-2px);
    }

    /* 인사이트 박스 */
    .insight-box {
        background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
        border-left: 5px solid #FF9800;
        padding: 20px;
        border-radius: 10px;
        color: #333;
        margin-bottom: 25px;
        font-size: 16px;
        line-height: 1.7;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    /* 섹션 헤더 */
    .section-header-container {
        display: flex;
        align-items: center;
        margin-top: 35px;
        margin-bottom: 20px;
        border-bottom: 3px solid #153d63;
        padding-bottom: 12px;
    }
    .section-badge {
        background: linear-gradient(135deg, #153d63 0%, #1a5280 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
        margin-right: 12px;
        box-shadow: 0 2px 6px rgba(21, 61, 99, 0.3);
    }
    .section-title-text {
        font-size: 24px;
        font-weight: 800;
        color: #153d63;
    }

    /* 계절 배지 */
    .season-badge {
        display: inline-block;
        background: linear-gradient(135deg, #FF6B6B 0%, #FFE66D 100%);
        color: #333;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 14px;
        margin-left: 15px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }

    /* 카드 스타일 */
    .pro-card {
        background: white !important;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e5e7eb;
        margin-bottom: 20px;
        transition: all 0.3s;
    }
    .pro-card:hover {
        box-shadow: 0 6px 16px rgba(21, 61, 99, 0.15);
        transform: translateY(-2px);
    }
    .card-header {
        font-size: 12px;
        font-weight: 700;
        color: #999;
        letter-spacing: 0.5px;
        margin-bottom: 10px;
        text-transform: uppercase;
    }
    .card-title {
        font-size: 28px;
        font-weight: 800;
        color: #153d63 !important;
        margin-bottom: 12px;
        line-height: 1.3;
    }
    .card-sub-metric {
        font-size: 14px;
        color: #666;
        line-height: 1.5;
    }
    .total-pop {
        font-size: 20px;
        font-weight: 700;
        color: #FF9800;
        margin-top: 8px;
    }

    /* 페르소나 인사이트 박스 */
    .persona-insight-box {
        background: linear-gradient(135deg, #E8EAF6 0%, #C5CAE9 100%);
        border-left: 5px solid #3F51B5;
        padding: 18px;
        border-radius: 10px;
        margin: 15px 0;
        font-size: 15px;
        line-height: 1.6;
        color: #333;
    }

    /* 키워드 아이템 */
    .keyword-item {
        background: white;
        border: 2px solid #e5e7eb;
        padding: 14px 16px;
        border-radius: 10px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s;
    }
    .keyword-item:hover {
        box-shadow: 0 4px 12px rgba(21, 61, 99, 0.15);
        border-color: #153d63;
        transform: translateX(4px);
    }
    .kwd-text {
        font-weight: 700;
        color: #333;
        font-size: 16px;
    }
    .kwd-vol {
        font-size: 14px;
        color: #666;
        font-weight: 600;
    }
    .kwd-comp {
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 12px;
        font-weight: 700;
        margin-left: 8px;
        text-transform: uppercase;
    }
    .comp-low { background: #C8E6C9; color: #2E7D32; }
    .comp-medium { background: #FFF9C4; color: #F57F17; }
    .comp-high { background: #FFCDD2; color: #C62828; }
    .kwd-tag {
        font-size: 11px;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 700;
        margin-left: 10px;
    }
    .tag-main {
        background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
        color: #1565C0;
    }
    .tag-conversion {
        background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
        color: #2E7D32;
    }

    /* 경쟁사 분석 카드 */
    .competitor-card {
        background: white;
        border: 2px solid #FFE0B2;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .competitor-header {
        font-size: 16px;
        font-weight: 700;
        color: #153d63;
        margin-bottom: 10px;
    }
    .competitor-level {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 700;
        margin-left: 10px;
    }
    .level-low { background: #C8E6C9; color: #2E7D32; }
    .level-medium { background: #FFF9C4; color: #F57F17; }
    .level-high { background: #FFCDD2; color: #C62828; }
    
    .competitor-blog-item {
        background: #f8f9fa;
        padding: 10px 12px;
        border-radius: 6px;
        margin: 8px 0;
        font-size: 13px;
        border-left: 3px solid #FF9800;
    }

    /* 전략 추천 카드 */
    .strategy-card {
        background: white;
        border: 2px solid #e5e7eb;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        transition: all 0.3s;
    }
    .strategy-card:hover {
        border-color: #153d63;
        box-shadow: 0 4px 12px rgba(21, 61, 99, 0.1);
    }
    .strategy-priority {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        margin-bottom: 10px;
    }
    .priority-HIGH { background: #FFCDD2; color: #C62828; }
    .priority-MEDIUM { background: #FFF9C4; color: #F57F17; }
    .priority-STRATEGIC { background: #E1BEE7; color: #6A1B9A; }
    .priority-SEASONAL { background: #FFE0B2; color: #E65100; }
    .priority-TARGET { background: #BBDEFB; color: #1565C0; }
    
    .strategy-title {
        font-size: 18px;
        font-weight: 700;
        color: #153d63;
        margin-bottom: 8px;
    }
    .strategy-desc {
        font-size: 14px;
        color: #666;
        line-height: 1.6;
        margin-bottom: 10px;
    }
    .strategy-action {
        background: #E3F2FD;
        padding: 10px;
        border-radius: 6px;
        font-size: 13px;
        color: #333;
        margin-bottom: 8px;
    }
    .strategy-result {
        font-size: 13px;
        color: #2E7D32;
        font-weight: 600;
    }

    /* 실행 계획 타임라인 */
    .timeline-container {
        position: relative;
        padding-left: 40px;
    }
    .timeline-item {
        background: white;
        border: 2px solid #e5e7eb;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        position: relative;
    }
    .timeline-item::before {
        content: '';
        position: absolute;
        left: -40px;
        top: 20px;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #153d63;
        border: 4px solid white;
        box-shadow: 0 0 0 2px #153d63;
    }
    .timeline-month {
        font-size: 18px;
        font-weight: 700;
        color: #153d63;
        margin-bottom: 8px;
    }
    .timeline-focus {
        font-size: 14px;
        color: #666;
        margin-bottom: 12px;
    }
    .timeline-actions {
        list-style: none;
        padding: 0;
    }
    .timeline-actions li {
        padding: 6px 0 6px 20px;
        position: relative;
        font-size: 14px;
        color: #333;
    }
    .timeline-actions li::before {
        content: '✓';
        position: absolute;
        left: 0;
        color: #2E7D32;
        font-weight: 700;
    }

    /* 콘텐츠 아이디어 카드 */
    .content-idea-card {
        background: white;
        border: 2px solid #e5e7eb;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        transition: all 0.3s;
    }
    .content-idea-card:hover {
        border-color: #153d63;
        box-shadow: 0 4px 12px rgba(21, 61, 99, 0.1);
    }
    .content-type-badge {
        display: inline-block;
        background: #153d63;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        margin-bottom: 10px;
    }
    .content-title {
        font-size: 16px;
        font-weight: 700;
        color: #764ba2;
        margin-bottom: 8px;
        line-height: 1.4;
    }
    .content-reason {
        font-size: 13px;
        color: #666;
        margin-bottom: 10px;
    }
    .content-guide {
        background: #F8F9FF;
        padding: 12px;
        border-radius: 6px;
        font-size: 13px;
        color: #333;
        line-height: 1.6;
    }

    /* 네이버 링크 */
    a.naver-link {
        text-decoration: none;
        color: #03C75A;
        font-weight: 700;
        font-size: 14px;
        margin-left: 10px;
        transition: all 0.2s;
    }
    a.naver-link:hover {
        color: #02A047;
        text-decoration: underline;
    }
    
    /* 사이드바 */
    .sidebar-logo-img {
        width: 60px;
        border-radius: 12px;
        margin-bottom: 8px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .sidebar-title {
        text-align: center;
        font-weight: 800;
        font-size: 17px;
        color: #153d63 !important;
        margin: 0 0 20px 0;
        line-height: 1.4;
    }
    .splash-logo {
        width: 140px;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }
    .main-title-logo {
        width: 50px;
        height: 50px;
        border-radius: 12px;
        margin-right: 15px;
        vertical-align: middle;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* 로딩 표시 */
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        text-align: center;
    }
    .loading-spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #153d63;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .loading-text {
        color: #153d63;
        font-weight: 600;
        font-size: 16px;
    }
</style>
""", unsafe_allow_html=True)

# --- 데이터 로드 ---
@st.cache_data
def load_cached_population_data():
    """인구 데이터 캐싱"""
    return load_population_data()

df = load_cached_population_data()

# --- 사이드바 ---
with st.sidebar:
    st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
    
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(
            f"""<div style="text-align:center; margin-bottom:15px;">
                <img src="data:image/png;base64,{img_b64}" class="sidebar-logo-img">
                <div class="sidebar-title">Brandiup<br>키워드 전략 분석</div>
            </div>""",
            unsafe_allow_html=True
        )
    
    st.markdown("---")
    st.header("📝 정보 입력")
    
    shop_name = st.text_input("🏪 가게명", "명가 닭국수", help="분석할 가게 이름을 입력하세요")
    
    category = st.selectbox(
        "📂 업종 카테고리",
        ["한식", "중식", "일식", "양식", "카페/디저트", "국수/면요리", "보양식", 
         "고기/구이", "술집", "분식", "치킨", "뷰티/미용", "숙박/펜션", "기타"],
        help="가게의 주요 업종을 선택하세요"
    )
    
    products = st.text_input(
        "🍜 대표 메뉴",
        "닭국수, 닭도리탕, 닭곰탕",
        help="주력 메뉴를 입력하세요 (콤마로 구분)"
    )
    
    tags_input = st.text_input(
        "🏷️ 가게 특징",
        "#해장 #비오는날 #든든한점심",
        help="가게의 특징을 #태그 형식으로 입력하세요"
    )
    
    st.markdown("---")
    st.markdown("**📍 분석 지역 선택**")
    
    sido_list = get_sido_list(df)
    idx_sido = sido_list.index("경기도") if "경기도" in sido_list else 0
    selected_sido = st.selectbox("시/도", sido_list, index=idx_sido)
    
    sigungu_list = get_sigungu_list(df, selected_sido)
    idx_sigungu = sigungu_list.index("용인시 처인구") if "용인시 처인구" in sigungu_list else 0
    selected_sigungu = st.selectbox("시/군/구", sigungu_list, index=idx_sigungu)
    
    dong_list = get_dong_list(df, selected_sido, selected_sigungu)
    selected_dongs = st.multiselect(
        "읍/면/동 (다중 선택)",
        dong_list,
        placeholder="분석할 상권을 선택하세요"
    )
    
    st.markdown("---")
    run_btn = st.button("🚀 전략 키워드 리포트 생성", type="primary", use_container_width=True)

# --- 메인 로직 ---
if run_btn:
    if not selected_dongs:
        st.error("❌ 분석할 지역을 선택해주세요.")
    else:
        # 로고 표시
        logo_path = "images/logo.png"
        img_html = ""
        if os.path.exists(logo_path):
            img_b64 = get_base64_of_bin_file(logo_path)
            img_html = f'<img src="data:image/png;base64,{img_b64}" class="main-title-logo">'
        
        current_season = get_current_season()
        current_date = datetime.now().strftime("%Y년 %m월 %d일")
        
        st.markdown(
            f"""<div style="display:flex; align-items:center; margin-bottom:25px;">
                {img_html}
                <h1 style="margin:0; padding:0; font-size:2.2rem; color:#153d63;">
                    Brandiup 상권 분석 리포트
                </h1>
                <span class="season-badge">{current_season} 시즌 🍂</span>
            </div>
            <div style="text-align:right; color:#666; font-size:14px; margin-bottom:20px;">
                분석일: {current_date}
            </div>""",
            unsafe_allow_html=True
        )

        # ===== SECTION 1: 인구 분석 =====
        agg_data = aggregate_population_data(df, selected_sido, selected_sigungu, selected_dongs)
        persona = get_persona_from_aggregated(agg_data)
        
        total_population = 0
        if agg_data:
            total_population = sum(sum(v.values()) for v in agg_data.values())

        loc_str = f"{selected_sigungu} {selected_dongs[0]}" + (
            f" 외 {len(selected_dongs)-1}곳" if len(selected_dongs) > 1 else ""
        )
        
        st.markdown(
            f"""<div class="section-header-container">
                <span class="section-badge">01</span>
                <span class="section-title-text">우리 동네 인구 분석 : {loc_str}</span>
            </div>""",
            unsafe_allow_html=True
        )
        
        # 핵심 타겟 정보
        st.markdown(f"""
        <div class='pro-card'>
            <div class='card-header'>🎯 Core Target</div>
            <div class='card-title'>{persona}</div>
            <hr style='margin:18px 0; border:0; border-top:2px solid #f0f2f6;'>
            <div class='card-header'>👥 Total Population</div>
            <div class='total-pop'>{total_population:,} 명</div>
            <div class='card-sub-metric' style='margin-top:8px;'>
                선택하신 상권의 총 거주 인구입니다.
            </div>
        </div>""", unsafe_allow_html=True)
        
        # 인구 차트
        if agg_data:
            chart_df = pd.DataFrame.from_dict(agg_data, orient='index').reset_index()
            chart_df.columns = ['연령대', '남성', '여성']
            chart_long = pd.melt(chart_df, id_vars=['연령대'], var_name='성별', value_name='인구수')
            
            c = alt.Chart(chart_long).mark_bar().encode(
                x=alt.X('연령대', axis=alt.Axis(labelAngle=0, title=None)),
                y=alt.Y(
                    '인구수', 
                    axis=alt.Axis(
                        title='인구수 (명)',
                        labelExpr="format(datum.value, ',.0f')"
                    )
                ),
                color=alt.Color(
                    '성별',
                    scale=alt.Scale(domain=['남성', '여성'], range=['#153d63', '#FF9800']),
                    legend=alt.Legend(title=None, orient='top')
                ),
                tooltip=[
                    alt.Tooltip('연령대', title='연령대'),
                    alt.Tooltip('성별', title='성별'),
                    alt.Tooltip('인구수', title='인구수', format=',')
                ]
            ).properties(height=400)
            
            st.altair_chart(c, use_container_width=True)

        # ===== SECTION 2: 키워드 분석 =====
        st.markdown(
            f"""<div class='section-header-container'>
                <span class='section-badge'>02</span>
                <span class='section-title-text'>전략 키워드 리포트</span>
            </div>""",
            unsafe_allow_html=True
        )
        
        # 로딩 표시
        progress_placeholder = st.empty()
        
        with progress_placeholder.container():
            st.markdown("""
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <div class="loading-text">🤖 AI가 키워드를 분석하고 있습니다...</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Step 1: AI 재료 추출
        materials = extract_keyword_materials(
            shop_name, products, category, tags_input, persona, loc_str
        )
        
        if materials:
            with progress_placeholder.container():
                st.markdown("""
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">📡 네이버 API로 검색량 & 경쟁사를 분석하고 있습니다...</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Step 2: 키워드 검증 + 경쟁사 분석
            report = generate_and_validate_keywords(
                loc_str, products, tags_input, materials, persona
            )
            
            progress_placeholder.empty()
            
            # 인사이트 박스
            insight_text = materials.get("insight", "데이터 분석 기반의 전략 제안입니다.")
            st.markdown(f"""
            <div class="insight-box">
                💡 <strong>AI Insight ({current_season} 시즌):</strong> {insight_text}
            </div>
            """, unsafe_allow_html=True)
            
            # 페르소나 인사이트
            persona_insight = materials.get("persona_insight", "")
            if persona_insight:
                st.markdown(f"""
                <div class="persona-insight-box">
                    👥 <strong>타겟 고객 분석:</strong> {persona_insight}
                </div>
                """, unsafe_allow_html=True)
            
            # 키워드 결과 출력
            col_main, col_detail = st.columns(2)
            
            # A. 메인 타겟 키워드
            with col_main:
                st.markdown("#### 📢 메인 타겟 키워드")
                st.caption("검색량이 많아 유입에 효과적인 키워드입니다.")
                
                if report['main_keywords']:
                    for item in report['main_keywords']:
                        comp_class = f"comp-{item.get('competition', 'low')}"
                        comp_text = {
                            'low': '낮음',
                            'medium': '보통',
                            'high': '높음'
                        }.get(item.get('competition', 'low'), '보통')
                        
                        is_estimated = item.get('is_estimated', False)
                        vol_display = f"🔥 {item['volume']:,}"
                        if is_estimated:
                            vol_display = f"📊 ~{item['volume']:,} (추정)"
                        
                        naver_url = f"https://search.naver.com/search.naver?query={item['keyword']}"
                        
                        st.markdown(f"""
                        <div class="keyword-item">
                            <div>
                                <span class="kwd-text">{item['keyword']}</span>
                                <span class="kwd-tag tag-main">메인</span>
                            </div>
                            <div style="display:flex; align-items:center;">
                                <span class="kwd-vol">{vol_display}</span>
                                <span class="kwd-comp {comp_class}">{comp_text}</span>
                                <a href="{naver_url}" target="_blank" class="naver-link">검색 →</a>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("⚠️ 조건에 맞는 메인 키워드를 찾지 못했습니다.")

            # B. 세부 공략 키워드
            with col_detail:
                st.markdown("#### 🎯 세부 공략 키워드")
                st.caption("구매 의도가 높은 타겟 맞춤형 키워드입니다.")
                
                if report['detail_keywords']:
                    for item in report['detail_keywords']:
                        comp_class = f"comp-{item.get('competition', 'low')}"
                        comp_text = {
                            'low': '낮음',
                            'medium': '보통',
                            'high': '높음'
                        }.get(item.get('competition', 'low'), '보통')
                        
                        is_estimated = item.get('is_estimated', False)
                        vol_display = f"🎯 {item['volume']:,}"
                        if is_estimated:
                            vol_display = f"📊 ~{item['volume']:,} (추정)"
                        
                        naver_url = f"https://search.naver.com/search.naver?query={item['keyword']}"
                        
                        st.markdown(f"""
                        <div class="keyword-item">
                            <div>
                                <span class="kwd-text">{item['keyword']}</span>
                                <span class="kwd-tag tag-conversion">전환형</span>
                            </div>
                            <div style="display:flex; align-items:center;">
                                <span class="kwd-vol">{vol_display}</span>
                                <span class="kwd-comp {comp_class}">{comp_text}</span>
                                <a href="{naver_url}" target="_blank" class="naver-link">검색 →</a>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("구체적인 세부 키워드를 찾지 못했습니다.")

            # ===== SECTION 3: 경쟁사 분석 =====
            if report.get('competitor_analysis'):
                st.markdown(
                    f"""<div class='section-header-container' style='margin-top:40px;'>
                        <span class='section-badge'>03</span>
                        <span class='section-title-text'>경쟁사 블로그 분석</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                
                st.markdown("**💡 이 분석을 통해 경쟁 강도를 파악하고 차별화 전략을 세울 수 있습니다.**")
                
                for comp in report['competitor_analysis']:
                    analysis = comp['analysis']
                    level_class = f"level-{analysis['competition_level']}"
                    level_text = {
                        'low': '경쟁 약함 ✅',
                        'medium': '중간 경쟁 ⚠️',
                        'high': '경쟁 치열 🔥'
                    }.get(analysis['competition_level'], '분석중')
                    
                    st.markdown(f"""
                    <div class="competitor-card">
                        <div class="competitor-header">
                            🔍 '{comp['keyword']}' 키워드 분석
                            <span class="competitor-level {level_class}">{level_text}</span>
                        </div>
                        <div style="margin:15px 0;">
                            <strong>총 블로그 포스팅:</strong> {analysis['total_posts']:,}개<br>
                            <strong>전략 제안:</strong> {analysis['strategy_insight']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if analysis['top_competitors']:
                        with st.expander(f"상위 노출 블로그 보기 ({len(analysis['top_competitors'])}개)"):
                            for blog in analysis['top_competitors']:
                                st.markdown(f"""
                                <div class="competitor-blog-item">
                                    <strong>{blog['rank']}위:</strong> {blog['title']}<br>
                                    <small>작성자: {blog['blogger']} | 날짜: {blog['date']}</small>
                                </div>
                                """, unsafe_allow_html=True)

            # ===== SECTION 4: 전략 추천 =====
            if report.get('strategic_recommendations'):
                st.markdown(
                    f"""<div class='section-header-container' style='margin-top:40px;'>
                        <span class='section-badge'>04</span>
                        <span class='section-title-text'>맞춤 전략 추천</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                
                st.markdown("**💼 이 전략대로만 실행하시면 3개월 내 결과를 보실 수 있습니다.**")
                
                for strategy in report['strategic_recommendations']:
                    priority_class = f"priority-{strategy['priority']}"
                    
                    st.markdown(f"""
                    <div class="strategy-card">
                        <span class="strategy-priority {priority_class}">{strategy['priority']} 우선순위</span>
                        <div class="strategy-title">🎯 {strategy['strategy']}</div>
                        <div class="strategy-desc">{strategy['description']}</div>
                        <div class="strategy-action">
                            <strong>실행 방법:</strong> {strategy['action']}
                        </div>
                        <div class="strategy-result">
                            📈 예상 결과: {strategy['expected_result']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # ===== SECTION 5: 3개월 실행 계획 =====
            if report.get('action_plan'):
                st.markdown(
                    f"""<div class='section-header-container' style='margin-top:40px;'>
                        <span class='section-badge'>05</span>
                        <span class='section-title-text'>3개월 실행 로드맵</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                
                action_plan = report['action_plan']
                
                st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
                
                for month_key in ['month_1', 'month_2', 'month_3']:
                    month_data = action_plan.get(month_key, {})
                    month_num = month_key.split('_')[1]
                    
                    actions_html = ''.join([f"<li>{action}</li>" for action in month_data.get('actions', [])])
                    
                    st.markdown(f"""
                    <div class="timeline-item">
                        <div class="timeline-month">📅 {month_num}개월차</div>
                        <div class="timeline-focus"><strong>핵심 목표:</strong> {month_data.get('focus', '')}</div>
                        <ul class="timeline-actions">
                            {actions_html}
                        </ul>
                        <div style="margin-top:12px; padding:10px; background:#E8F5E9; border-radius:6px; font-size:13px; color:#2E7D32;">
                            <strong>✅ 예상 성과:</strong> {month_data.get('expected', '')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)

            # ===== SECTION 6: 콘텐츠 아이디어 =====
            if report.get('content_ideas'):
                st.markdown(
                    f"""<div class='section-header-container' style='margin-top:40px;'>
                        <span class='section-badge'>06</span>
                        <span class='section-title-text'>콘텐츠 제작 가이드</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                
                st.markdown("**✍️ 바로 사용 가능한 블로그/SNS 콘텐츠 아이디어입니다.**")
                
                for idea in report['content_ideas']:
                    st.markdown(f"""
                    <div class="content-idea-card">
                        <span class="content-type-badge">{idea['type']}</span>
                        <div class="content-title">{idea['title']}</div>
                        <div class="content-reason">📊 {idea['reason']}</div>
                        <div class="content-guide">
                            <strong>📝 작성 가이드:</strong><br>
                            {idea.get('content_guide', '자유롭게 작성하세요')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
        else:
            progress_placeholder.empty()
            st.error("❌ AI 분석에 실패했습니다. OpenAI API 키를 확인해주세요.")

else:
    # 초기 화면
    logo_path = "images/logo.png"
    if os.path.exists(logo_path):
        img_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(
            f"""<div style="display:flex; justify-content:center; align-items:center; height:70vh;">
                <img src="data:image/png;base64,{img_b64}" class="splash-logo">
            </div>""",
            unsafe_allow_html=True
        )