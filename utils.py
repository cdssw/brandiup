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

def get_current_season_context():
    month = datetime.now().month
    if 3 <= month <= 5: return "봄 (벚꽃, 나들이, 입맛)"
    elif 6 <= month <= 8: return "여름 (보양, 이열치열, 비, 휴가)"
    elif 9 <= month <= 11: return "가을 (단풍, 국물, 축제)"
    else: return "겨울 (뜨끈한, 추위, 연말)"

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

def get_keyword_volume(keyword):
    if not ADS_API_KEY: return []
    uri = "/keywordstool"
    method = "GET"
    try:
        headers = get_header(method, uri, ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
        params = {"hintKeywords": keyword.replace(" ", ""), "showDetail": 1}
        res = requests.get(ADS_BASE_URL + uri, params=params, headers=headers)
        if res.status_code == 200:
            return res.json().get("keywordList", [])
    except:
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

def generate_keywords_with_ai(shop_name, location, category, persona):
    if not client: return None
    season = get_current_season_context()
    
    prompt = f"""
    역할: 마케팅 전문가.
    가게: {shop_name} ({category}) / 지역: {location}
    타겟: {persona} / 시즌: {season}

    임무: 이 가게를 위한 '3단계 키워드 전략'을 수립하세요.
    각 단계별로 후보 키워드를 5개씩 뽑아주세요.

    [단계별 정의]
    1. 광역(소문내기): 검색량이 가장 많은 지역 대표 키워드 (예: 용인 맛집)
    2. 카테고리(뺏어오기): 경쟁 가게를 찾는 사람을 유인 (예: 용인 칼국수)
    3. 틈새(이기기): 구체적인 상황/니즈, 무조건 잡을 수 있는 키워드 (예: 포곡읍 해장, 처인구 비오는날)

    형식(JSON):
    {{
        "1단계_후보": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
        "2단계_후보": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
        "3단계_후보": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
        "추천_제목": ["제목1", "제목2", "제목3"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return response.choices[0].message.content
    except:
        return None