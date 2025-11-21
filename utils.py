import time
import hmac
import hashlib
import base64
import requests
import urllib.parse
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

ADS_API_KEY = os.environ.get("NAVER_ADS_API_KEY")
ADS_SECRET_KEY = os.environ.get("NAVER_ADS_SECRET_KEY")
CUSTOMER_ID = os.environ.get("NAVER_CUSTOMER_ID")
SEARCH_CLIENT_ID = os.environ.get("NAVER_SEARCH_CLIENT_ID")
SEARCH_CLIENT_SECRET = os.environ.get("NAVER_SEARCH_CLIENT_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

ADS_BASE_URL = "https://api.naver.com"

client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(int(time.time() * 1000))
    signature = hmac.new(
        bytes(secret_key, "utf-8"),
        bytes(f"{timestamp}.{method}.{uri}", "utf-8"),
        hashlib.sha256
    ).digest()
    return {
        "X-Timestamp": timestamp,
        "X-API-KEY": api_key,
        "X-Customer": customer_id,
        "X-Signature": base64.b64encode(signature).decode("utf-8"),
    }

def get_related_keywords(seed_keywords):
    if not ADS_API_KEY: return []
    
    if isinstance(seed_keywords, list):
        hint_keywords = ",".join(seed_keywords)
    else:
        hint_keywords = seed_keywords

    hint_keywords = hint_keywords.replace(" ", "")
    
    uri = "/keywordstool"
    method = "GET"
    try:
        headers = get_header(method, uri, ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
        params = {"hintKeywords": hint_keywords, "showDetail": 1}
        res = requests.get(ADS_BASE_URL + uri, params=params, headers=headers)
        
        if res.status_code == 200:
            data = res.json().get("keywordList", [])
            cleaned_data = []
            for item in data:
                kwd = item['relKeyword']
                pc = item['monthlyPcQcCnt']
                mo = item['monthlyMobileQcCnt']
                if isinstance(pc, str): pc = 0
                if isinstance(mo, str): mo = 0
                total = pc + mo
                
                # [필터링 강화]
                # 1. 검색량 30 미만 제외 (너무 0인 것)
                # 2. 검색량 30,000 초과 제외 (소상공인이 못 잡는 너무 큰 키워드)
                if total < 30 or total > 30000: continue
                
                cleaned_data.append({"keyword": kwd, "volume": total})
            
            cleaned_data.sort(key=lambda x: x['volume'], reverse=True)
            return cleaned_data
            
    except Exception as e:
        print(f"API Error: {e}")
        pass
    return []

def get_blog_search_result(keyword):
    if not SEARCH_CLIENT_ID: return {"total": 0, "items": []}
    url = f"https://openapi.naver.com/v1/search/blog.json?query={urllib.parse.quote(keyword)}&display=3&sort=sim"
    headers = {
        "X-Naver-Client-Id": SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            return {"total": data.get("total", 0), "items": data.get("items", [])}
    except:
        pass
    return {"total": 0, "items": []}

def select_best_keywords_with_ai(shop_name, location, products, persona, keyword_list):
    if not client: return None
    
    # [소상공인 맞춤형 구간 재설정]
    # High (Step 1): 1,000 ~ 20,000 (현실적인 대형)
    # Mid (Step 2): 300 ~ 2,000 (알짜 중형)
    # Low (Step 3): 50 ~ 500 (확실한 틈새)
    
    high_tier = [] 
    mid_tier = []  
    low_tier = []  
    
    for item in keyword_list:
        vol = item['volume']
        if 1000 <= vol <= 20000: high_tier.append(item)
        elif 300 <= vol < 2000: mid_tier.append(item)
        elif 50 <= vol < 500: low_tier.append(item)
    
    # 구간별 데이터가 없을 경우 인접 구간에서 보충 (Fallback)
    if not high_tier: high_tier = mid_tier[:10]
    if not mid_tier: mid_tier = high_tier[-5:] + low_tier[:5]
    if not low_tier: low_tier = mid_tier[-10:]
    
    # AI에게 보낼 데이터 (상위권 위주로 자름)
    prompt_data = {
        "Group_A_Exposure": high_tier[:15],  # 노출용
        "Group_B_Traffic": mid_tier[:15],    # 유입용
        "Group_C_Niche": low_tier[:15]       # 틈새용
    }
    
    data_str = json.dumps(prompt_data, ensure_ascii=False)
    
    prompt = f"""
    역할: 소상공인 마케팅 전략가.
    가게: {shop_name} ({products}) / 지역: {location}
    타겟: {persona}

    [상황]
    우리는 대기업이 아닙니다. '맛집' 같은 초대형 키워드는 경쟁이 심해 노출되지 않습니다.
    **소상공인이 실제로 상위 노출을 노려볼 수 있는 '현실적인 실속 키워드'**를 골라야 합니다.

    [제공 데이터 (검색량별 그룹)]
    {data_str}

    [임무]
    위 리스트 중에서 각 단계별 최고의 키워드를 하나씩 선택하세요.
    
    1. **Step 1 (가게 알리기):** 'Group_A'에서 선택. 너무 뻔한 지역명(예: 용인맛집)보다는, 구체적인 지명이나 메뉴가 결합된 키워드(예: 처인구 칼국수)를 우선하세요.
    2. **Step 2 (손님 뺏기):** 'Group_B'에서 선택. 경쟁 가게나 유사 메뉴를 찾는 사람들이 검색하는 단어.
    3. **Step 3 (구매 전환):** 'Group_C'에서 선택. 검색량은 적지만 방문 의사가 확실한 구체적인 단어(상황/니즈).

    형식(JSON):
    {{
        "1단계_선정": {{"keyword": "키워드명", "volume": 숫자, "reason": "선정이유"}},
        "2단계_선정": {{"keyword": "키워드명", "volume": 숫자, "reason": "선정이유"}},
        "3단계_선정": {{"keyword": "키워드명", "volume": 숫자, "reason": "선정이유"}},
        "추천_제목": ["제목1", "제목2", "제목3"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4 # 창의성 더 낮춤 (데이터 준수)
        )
        return response.choices[0].message.content
    except:
        return None