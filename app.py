import streamlit as st
import pandas as pd
import json
import time
import re
import altair as alt
from utils import get_keyword_volume, get_blog_search_result, generate_keywords_with_ai
from data_loader import load_population_data, get_region_persona, get_population_chart_data

st.set_page_config(page_title="브랜디업 솔루션 리포트", layout="wide")

# --- CSS 디자인 ---
st.markdown("""
<style>
    .report-container { padding: 20px; }
    .pro-card {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
        color: #333333 !important;
        height: 100%; /* 높이 맞춤 */
    }
    .pro-card h1, .pro-card h2, .pro-card h3, .pro-card h4, .pro-card p, .pro-card div, .pro-card span {
        color: #333333 !important;
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
        font-size: 24px;
        font-weight: 800;
        color: #1E3A8A !important;
        margin-bottom: 15px;
        min-height: 60px; /* 타이틀 높이 고정 */
        display: flex;
        align-items: center;
    }
    .solution-box {
        background-color: #F0F9FF !important;
        border-left: 5px solid #2563EB;
        padding: 20px;
        border-radius: 4px;
    }
    /* 경고 카드 스타일 (검색량 0일 때) */
    .warning-card {
        background-color: #FFF4E5 !important;
        border: 1px solid #FFCC80;
    }
    hr { margin: 20px 0; border-color: #eee; }
</style>
""", unsafe_allow_html=True)

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def pick_best_keyword(keyword_list, strategy_type):
    if not keyword_list:
        return {"키워드": "데이터 없음", "월간검색": 0, "문서수": 0, "상위글": []}

    best_data = None
    max_val = -9999 # 초기값 설정
    
    # 유효한 키워드(검색량 > 0)가 하나라도 있는지 체크
    has_valid_keyword = False

    for kwd in keyword_list:
        # 1. 데이터 조회
        vol_list = get_keyword_volume(kwd)
        search_vol = 0
        if vol_list:
            item = vol_list[0]
            pc = item['monthlyPcQcCnt']
            mo = item['monthlyMobileQcCnt']
            if isinstance(pc, str): pc = 0
            if isinstance(mo, str): mo = 0
            search_vol = pc + mo
            
        blog_info = get_blog_search_result(kwd)
        doc_count = blog_info['total']
        
        # 2. 점수 로직 (검색량이 0이면 아주 낮은 점수 부여)
        score = 0
        
        if search_vol > 0:
            has_valid_keyword = True
            if strategy_type == "volume": 
                score = search_vol
            elif strategy_type == "balance":
                score = search_vol / (doc_count + 50) # 분모 보정
            elif strategy_type == "efficiency":
                # 효율이 좋아도 검색량이 너무 적으면(예: 10) 점수 깎음
                if search_vol < 30: score = 0.1 
                else: score = search_vol / (doc_count + 1)
        else:
            # 검색량이 0인 경우 점수 대폭 삭감
            score = -1
        
        current_data = {
            "키워드": kwd, 
            "월간검색": search_vol, 
            "문서수": doc_count, 
            "상위글": blog_info['items']
        }

        if score > max_val:
            max_val = score
            best_data = current_data
            
        time.sleep(0.05) # API 보호

    # 만약 모든 키워드가 0건이면(has_valid_keyword=False), 어쩔 수 없이 마지막 거라도 리턴하지만
    # 화면에서 처리하기 위해 0 그대로 보냄
    if best_data is None:
        best_data = {"키워드": keyword_list[0], "월간검색": 0, "문서수": 0, "상위글": []}
        
    return best_data

# --- 메인 앱 ---

st.title("📊 BrandiUp 상권 분석 리포트")

if 'pop_df' not in st.session_state:
    st.session_state['pop_df'] = load_population_data()

with st.sidebar:
    st.header("진단 설정")
    shop_name = st.text_input("가게명", "명가 닭국수")
    location = st.text_input("지역 (동/읍 단위)", "용인시 처인구 포곡읍")
    category = st.text_input("업종", "닭국수")
    # [요청] 버튼 크기 맞춤
    run_btn = st.button("분석 리포트 생성 🚀", type="primary", use_container_width=True)

if run_btn:
    # 1. 인구 분석
    df_pop = st.session_state['pop_df']
    persona = get_region_persona(location, df_pop)
    chart_data = get_population_chart_data(location, df_pop)
    
    st.markdown("---")
    # [요청] 쉬운 한글 용어
    st.subheader(f"1️⃣ 우리 동네 인구 분석: {location.split()[-1]}")
    
    col_demo_1, col_demo_2 = st.columns([1, 2])
    
    with col_demo_1:
        st.markdown(f"""
        <div class='pro-card'>
            <div class='card-header'>핵심 고객 (Core Target)</div>
            <div class='card-title' style='font-size: 28px;'>{persona}</div>
            <hr>
            <div class='card-sub-metric'>
                우리 동네 거주 인구 데이터를 분석했을 때<br>
                가장 많이 사는 <b>주요 고객층</b>입니다.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_demo_2:
        if chart_data:
            st.markdown("##### 📊 연령별/성별 인구 분포")
            # [요청] 차트 가로 보기
            chart_df = pd.DataFrame.from_dict(chart_data, orient='index').reset_index()
            chart_df.columns = ['연령대', '남성', '여성']
            chart_long = pd.melt(chart_df, id_vars=['연령대'], var_name='성별', value_name='인구수')
            
            c = alt.Chart(chart_long).mark_bar().encode(
                x=alt.X('연령대', axis=alt.Axis(labelAngle=0, title=None)),
                y=alt.Y('인구수', axis=alt.Axis(title=None)),
                color=alt.Color('성별', scale=alt.Scale(domain=['남성', '여성'], range=['#4285F4', '#FF5252'])),
                tooltip=['연령대', '성별', '인구수']
            ).properties(height=300)
            st.altair_chart(c, use_container_width=True)
        else:
            st.warning("인구 데이터를 불러올 수 없습니다.")

    # 2. 전략 수립
    st.markdown("---")
    st.subheader("2️⃣ 맞춤형 키워드 전략")
    
    with st.spinner("AI가 최적의 마케팅 전략을 짜고 있습니다..."):
        ai_result = generate_keywords_with_ai(shop_name, location, category, persona)
        
        if ai_result:
            try:
                ai_data = json.loads(ai_result)
                
                c1, c2, c3 = st.columns(3)
                
                # STEP 1. 인지도 (광역)
                with c1:
                    best_1 = pick_best_keyword(ai_data.get("1단계_후보", []), "volume")
                    st.markdown(f"""
                    <div class='pro-card'>
                        <div class='card-header'>STEP 1. 가게 알리기 (노출)</div>
                        <div class='card-title'>{best_1['키워드']}</div>
                        <div>월간 검색량 <span style='font-weight:bold;'>{best_1['월간검색']:,}</span>건</div>
                        <div>블로그 문서 <span style='font-weight:bold;'>{best_1['문서수']:,}</span>개</div>
                        <hr>
                        <div class='card-sub-metric'>
                            가장 많은 사람이 검색하는 <b>대표 키워드</b>입니다.
                            우리 가게 이름을 알리는 데 가장 효과적입니다.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # STEP 2. 유입 (카테고리)
                with c2:
                    best_2 = pick_best_keyword(ai_data.get("2단계_후보", []), "balance")
                    st.markdown(f"""
                    <div class='pro-card'>
                        <div class='card-header'>STEP 2. 손님 뺏어오기 (유입)</div>
                        <div class='card-title'>{best_2['키워드']}</div>
                        <div>월간 검색량 <span style='font-weight:bold;'>{best_2['월간검색']:,}</span>건</div>
                        <div>블로그 문서 <span style='font-weight:bold;'>{best_2['문서수']:,}</span>개</div>
                        <hr>
                        <div class='card-sub-metric'>
                            경쟁 가게를 찾는 손님을 <b>우리 가게로 오게 만드는</b> 키워드입니다.
                            메뉴를 고민하는 손님을 공략합니다.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # STEP 3. 틈새 (효율) - 0건일 경우 처리 로직 추가
                with c3:
                    best_3 = pick_best_keyword(ai_data.get("3단계_후보", []), "efficiency")
                    
                    # 검색량이 0이면 거짓말하지 않고 솔직하게 '발굴 실패' 혹은 '데이터 부족'으로 표시
                    if best_3['월간검색'] == 0:
                         st.markdown(f"""
                        <div class='pro-card warning-card'>
                            <div class='card-header' style='color:#E65100 !important;'>STEP 3. 틈새 공략</div>
                            <div class='card-title' style='color:#BF360C !important; font-size:20px;'>발굴된 틈새 없음</div>
                            <div>월간 검색량 <span style='font-weight:bold;'>0</span>건</div>
                            <div>블로그 문서 <span style='font-weight:bold;'>{best_3['문서수']:,}</span>개</div>
                            <hr>
                            <div class='card-sub-metric'>
                                현재 조건으로는 검색량이 유의미한 틈새 키워드가 없습니다.
                                <b>STEP 1, 2 전략에 집중</b>하는 것을 추천합니다.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # 정상적으로 틈새 키워드가 있을 때
                        st.markdown(f"""
                        <div class='pro-card' style='border: 2px solid #2563EB;'>
                            <div class='card-header' style='color:#2563EB !important;'>STEP 3. 단골 만들기 (핵심)</div>
                            <div class='card-title' style='color:#D32F2F !important;'>{best_3['키워드']}</div>
                            <div>월간 검색량 <span style='font-weight:bold;'>{best_3['월간검색']:,}</span>건</div>
                            <div>블로그 문서 <span style='font-weight:bold;'>{best_3['문서수']:,}</span>개</div>
                            <hr>
                            <div class='card-sub-metric'>
                                경쟁은 적은데 찾는 사람은 확실한 <b>알짜배기 키워드</b>입니다.
                                지금 글을 쓰면 상위에 뜰 확률이 높습니다.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # 솔루션 제안 (Step 3가 0건일 때 멘트 변경)
                step3_msg = ""
                if best_3['월간검색'] > 0:
                    step3_msg = f"3. <b>'{best_3['키워드']}'</b>로 확실하게 방문을 유도합니다."
                else:
                    step3_msg = "3. (현재 틈새 키워드보다 대형 키워드 노출이 더 시급합니다)"

                st.markdown(f"""
                <div class='pro-card solution-box'>
                    <h3 style='color:#1E3A8A !important;'>💡 BrandiUp 솔루션 제안</h3>
                    <p>
                        사장님, 성공적인 마케팅을 위해 <b>단계별 전략</b>을 제안합니다.<br><br>
                        1. <b>'{best_1['키워드']}'</b>로 동네에 가게 이름을 널리 알리고,<br>
                        2. <b>'{best_2['키워드']}'</b>로 메뉴를 고민하는 손님을 잡고,<br>
                        {step3_msg}
                    </p>
                </div>
                """, unsafe_allow_html=True)

                # 3. 경쟁사 분석
                st.markdown("---")
                st.subheader("3️⃣ 경쟁 가게 분석")
                
                # Step 3가 유효하면 Step 3, 아니면 Step 2 키워드로 분석 보여줌
                target_kwd = best_3 if best_3['월간검색'] > 0 else best_2
                
                st.caption(f"'{target_kwd['키워드']}' 검색 시 1페이지에 나오는 다른 블로그 글입니다.")

                if target_kwd['상위글']:
                    cols = st.columns(3)
                    for idx, post in enumerate(target_kwd['상위글']):
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
                    st.info("현재 이 키워드를 제대로 잡고 있는 경쟁자가 없습니다. 기회입니다!")

                # 4. 가이드라인
                st.markdown("---")
                st.subheader("4️⃣ 블로그 제목 추천")
                st.caption("손님이 클릭하고 싶게 만드는 매력적인 제목입니다.")
                
                # [요청] 제목 3개만
                recommended_titles = ai_data.get("추천_제목", [])[:3]
                for t in recommended_titles:
                    st.success(f"✅ {t}")
            
            except Exception as e:
                st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")

        else:
            st.error("분석 시스템 연결 실패. API 설정을 확인해주세요.")