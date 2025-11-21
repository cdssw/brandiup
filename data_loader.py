import pandas as pd
import os

def load_population_data(csv_path="data/population.csv"):
    """CSV 파일 로드"""
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path, encoding='cp949')
    except:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
        except:
            return None
    return df

def get_target_row(location, df):
    """지역명으로 행 찾기"""
    if df is None: return None
    dong_name = location.split()[-1]
    try:
        # 유연하게 컬럼 찾기
        target_cols = [col for col in df.columns if '동명' in col or '행정' in col or '시군구' in col]
        for col in target_cols:
            matches = df[df[col].astype(str).str.contains(dong_name, na=False)]
            if not matches.empty:
                return matches.iloc[0]
    except:
        pass
    return None

def get_region_persona(location, df):
    """핵심 타겟(페르소나) 텍스트 반환"""
    target_row = get_target_row(location, df)
    if target_row is None: return "데이터 없음 (일반 대중)"

    # 나이대별 합산
    age_groups = {"10대": 0, "20대": 0, "30대": 0, "40대": 0, "50대": 0, "60대이상": 0}
    
    for col in df.columns:
        if ('세남자' in col or '세여자' in col) and '계' not in col:
            try:
                age_str = ''.join(filter(str.isdigit, col))
                if not age_str: continue
                age = int(age_str)
                val = int(str(target_row[col]).replace(',', ''))
                
                if 10 <= age < 20: age_groups["10대"] += val
                elif 20 <= age < 30: age_groups["20대"] += val
                elif 30 <= age < 40: age_groups["30대"] += val
                elif 40 <= age < 50: age_groups["40대"] += val
                elif 50 <= age < 60: age_groups["50대"] += val
                elif age >= 60: age_groups["60대이상"] += val
            except:
                continue

    if sum(age_groups.values()) == 0: return "분석 불가"
    top_age = max(age_groups, key=age_groups.get)
    
    # 성별 분석
    try:
        male = int(str(target_row.get('남자', 0)).replace(',', ''))
        female = int(str(target_row.get('여자', 0)).replace(',', ''))
        gender = "남녀 고름"
        if male > female * 1.1: gender = "남성"
        elif female > male * 1.1: gender = "여성"
    except:
        gender = "성별무관"

    return f"{top_age} {gender} 거주 지역"

def get_population_chart_data(location, df):
    """
    [수정됨] 성별/연령별 데이터를 구분해서 반환
    Return 예시: {'10대': {'남성': 100, '여성': 120}, ...}
    """
    target_row = get_target_row(location, df)
    if target_row is None: return {}

    # 데이터 구조 변경: 나이대별로 [남성수, 여성수] 저장
    # 초기화
    data = {
        "10대": {"남성": 0, "여성": 0},
        "20대": {"남성": 0, "여성": 0},
        "30대": {"남성": 0, "여성": 0},
        "40대": {"남성": 0, "여성": 0},
        "50대": {"남성": 0, "여성": 0},
        "60대+": {"남성": 0, "여성": 0},
    }
    
    for col in df.columns:
        # 컬럼명 예: "20세남자", "20세여자"
        if ('세남자' in col or '세여자' in col) and '계' not in col:
            try:
                age_str = ''.join(filter(str.isdigit, col))
                if not age_str: continue
                age = int(age_str)
                val = int(str(target_row[col]).replace(',', ''))
                
                # 성별 판별
                gender_key = "남성" if "남자" in col else "여성"
                
                # 그룹핑
                group_key = ""
                if 10 <= age < 20: group_key = "10대"
                elif 20 <= age < 30: group_key = "20대"
                elif 30 <= age < 40: group_key = "30대"
                elif 40 <= age < 50: group_key = "40대"
                elif 50 <= age < 60: group_key = "50대"
                elif age >= 60: group_key = "60대+"
                
                if group_key:
                    data[group_key][gender_key] += val
            except:
                continue
    
    # 전체 인구수 계산 (비율 계산용)
    total_population = sum(d['남성'] + d['여성'] for d in data.values())
    
    if total_population == 0: return {}

    # 값을 퍼센트(%)로 변환하여 반환 (선택사항: 숫자로 보고 싶으면 이 부분 조정)
    # 여기서는 차트의 가독성을 위해 '실제 인구수'를 반환하는 게 시각적으로 더 좋습니다.
    # (Streamlit 차트가 알아서 비율을 보여주기도 함)
    return data