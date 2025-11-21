import pandas as pd
import os
import streamlit as st

@st.cache_data
def load_population_data(csv_path="data/population.csv"):
    """CSV 로드 및 컬럼명 표준화"""
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path, encoding='cp949')
    except:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
        except:
            return None
            
    # 공공데이터 컬럼명 표준화 (혹시 다를 경우를 대비)
    # 보통: 행정기관코드, 시도명, 시군구명, 읍면동명
    return df

def get_sido_list(df):
    """시도 목록 추출"""
    if df is None: return []
    return sorted(df['시도명'].unique().tolist())

def get_sigungu_list(df, sido):
    """선택된 시도의 시군구 목록 추출"""
    if df is None: return []
    filtered = df[df['시도명'] == sido]
    return sorted(filtered['시군구명'].unique().tolist())

def get_dong_list(df, sido, sigungu):
    """선택된 시군구의 읍면동 목록 추출"""
    if df is None: return []
    filtered = df[(df['시도명'] == sido) & (df['시군구명'] == sigungu)]
    return sorted(filtered['읍면동명'].unique().tolist())

def aggregate_population_data(df, sido, sigungu, dong_list):
    """
    선택된 여러 읍면동의 데이터를 합산(Aggregation)하여
    하나의 가상 데이터(Row)로 만듦
    """
    if df is None or not dong_list: return None
    
    # 선택된 행들 필터링
    condition = (df['시도명'] == sido) & (df['시군구명'] == sigungu) & (df['읍면동명'].isin(dong_list))
    filtered_df = df[condition]
    
    if filtered_df.empty: return None

    # 나이/성별 데이터 합산
    # 숫자 컬럼만 다 더함
    aggregated_data = {
        "10대": {"남성": 0, "여성": 0},
        "20대": {"남성": 0, "여성": 0},
        "30대": {"남성": 0, "여성": 0},
        "40대": {"남성": 0, "여성": 0},
        "50대": {"남성": 0, "여성": 0},
        "60대+": {"남성": 0, "여성": 0},
    }
    
    # 원본 데이터 순회하며 합산
    for _, row in filtered_df.iterrows():
        for col in df.columns:
            if ('세남자' in col or '세여자' in col) and '계' not in col:
                try:
                    age_str = ''.join(filter(str.isdigit, col))
                    if not age_str: continue
                    age = int(age_str)
                    
                    # 데이터 클렌징 (콤마 제거)
                    val = int(str(row[col]).replace(',', ''))
                    
                    gender_key = "남성" if "남자" in col else "여성"
                    
                    group_key = ""
                    if 10 <= age < 20: group_key = "10대"
                    elif 20 <= age < 30: group_key = "20대"
                    elif 30 <= age < 40: group_key = "30대"
                    elif 40 <= age < 50: group_key = "40대"
                    elif 50 <= age < 60: group_key = "50대"
                    elif age >= 60: group_key = "60대+"
                    
                    if group_key:
                        aggregated_data[group_key][gender_key] += val
                except:
                    continue
                    
    return aggregated_data

def get_persona_from_aggregated(agg_data):
    """합산된 데이터를 바탕으로 페르소나 텍스트 생성"""
    if not agg_data: return "데이터 없음"
    
    # 세대별 총합 계산
    age_totals = {k: sum(v.values()) for k, v in agg_data.items()}
    top_age = max(age_totals, key=age_totals.get)
    
    # 성별 총합 계산
    total_male = sum(v['남성'] for v in agg_data.values())
    total_female = sum(v['여성'] for v in agg_data.values())
    
    gender = "남녀 고름"
    if total_male > total_female * 1.1: gender = "남성"
    elif total_female > total_male * 1.1: gender = "여성"
    
    return f"{top_age} {gender} 주거 상권"