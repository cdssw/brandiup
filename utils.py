import time
import hmac
import hashlib
import base64
import requests
import urllib.parse
import os
from dotenv import load_dotenv # 추가된 부분

# .env 파일이 있으면 로드 (로컬 개발용)
load_dotenv()

# 환경변수 가져오기 (로컬에서는 .env에서, Docker에서는 -e 옵션에서 가져옴)
ADS_API_KEY = os.environ.get("NAVER_ADS_API_KEY")
ADS_SECRET_KEY = os.environ.get("NAVER_ADS_SECRET_KEY")
CUSTOMER_ID = os.environ.get("NAVER_CUSTOMER_ID")
SEARCH_CLIENT_ID = os.environ.get("NAVER_SEARCH_CLIENT_ID")
SEARCH_CLIENT_SECRET = os.environ.get("NAVER_SEARCH_CLIENT_SECRET")

ADS_BASE_URL = "https://api.naver.com"

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
    """검색광고 API: 연관 키워드 및 검색량 조회"""
    if not ADS_API_KEY: return [] # 키가 없으면 빈 리스트 반환

    uri = "/keywordstool"
    method = "GET"
    headers = get_header(method, uri, ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
    
    params = {"hintKeywords": keyword.replace(" ", ""), "showDetail": 1}
    try:
        res = requests.get(ADS_BASE_URL + uri, params=params, headers=headers)

        if res.status_code != 200:
            print(f"❌ API Error: {res.status_code}")
            print(f"❌ Response: {res.text}") # 여기에 'IP가 등록되지 않음' 같은 메시지가 뜹니다.
                    
        if res.status_code == 200:
            return res.json().get("keywordList", [])
    except:
        pass
    return []

def get_blog_count(keyword):
    """검색 API: 블로그 문서수 조회"""
    if not SEARCH_CLIENT_ID: return 0

    url = f"https://openapi.naver.com/v1/search/blog.json?query={urllib.parse.quote(keyword)}&display=1&sort=sim"
    headers = {
        "X-Naver-Client-Id": SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get("total", 0)
    except:
        pass
    return 0