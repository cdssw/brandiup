import time
import hmac
import hashlib
import base64
import requests
import urllib.parse

# 네이버 검색광고 API 정보 (본인 것으로 교체)
ADS_API_KEY = "YOUR_ADS_API_KEY"
ADS_SECRET_KEY = "YOUR_ADS_SECRET_KEY"
CUSTOMER_ID = "YOUR_CUSTOMER_ID"
ADS_BASE_URL = "https://api.naver.com"

# 네이버 검색(개발자센터) API 정보 (본인 것으로 교체)
SEARCH_CLIENT_ID = "YOUR_CLIENT_ID"
SEARCH_CLIENT_SECRET = "YOUR_CLIENT_SECRET"

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
    """검색광고 API를 통해 연관 키워드와 검색량을 가져옴"""
    uri = "/keywordstool"
    method = "GET"
    headers = get_header(method, uri, ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
    
    # 공백 제거하여 요청
    params = {"hintKeywords": keyword.replace(" ", ""), "showDetail": 1}
    res = requests.get(ADS_BASE_URL + uri, params=params, headers=headers)
    
    if res.status_code == 200:
        return res.json().get("keywordList", [])
    else:
        return []

def get_blog_count(keyword):
    """네이버 검색 API를 통해 블로그 문서(Total) 수를 가져옴"""
    url = f"https://openapi.naver.com/v1/search/blog.json?query={urllib.parse.quote(keyword)}&display=1&sort=sim"
    headers = {
        "X-Naver-Client-Id": SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET
    }
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json().get("total", 0)
    return 0