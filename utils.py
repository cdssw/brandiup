import time
import hmac
import hashlib
import base64
import requests
import urllib.parse
import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# ---------------------------------------------------------
# [NEW] 1단계: AI에게 재료(유사어, 타겟키워드 등)만 받기
# ---------------------------------------------------------
def extract_keyword_materials(shop_name, products, category, tags, persona, location):
    if not client: return None
    
    prompt = f"""
    역할: 마케팅 데이터 분석가.
    가게: {shop_name}
    업종: {category}
    메뉴: {products}
    타겟: {persona}
    태그: {tags}

    임무: 키워드 확장을 위한 '재료 단어'들을 추출하세요.
    
    [규칙]
    1. similar_menus: '{products}'보다 검색량이 더 많을 것 같은 대중적인 유사 메뉴명 3개. (예: 닭국수 -> 닭칼국수, 삼계탕)
    2. category_keywords: 업종을 대표하는 일반 명사 3개. (예: 국수, 한식, 보양식, 점심)
    3. target_keywords: '{persona}'가 좋아할 만한 수식어 3개. (예: 30대 남성 -> 가성비, 회식, 해장 / 20대 여성 -> 분위기, 데이트)
    4. insight: 왜 '{products}' 대신 'similar_menus[0]'을 써야 하는지 짧은 한 줄 설명.

    형식(JSON):
    {{
        "similar_menus": ["단어1", "단어2", "단어3"],
        "category_keywords": ["단어1", "단어2", "단어3"],
        "target_keywords": ["단어1", "단어2", "단어3"],
        "insight": "고객들은 닭국수보다 닭칼국수를 더 많이 검색합니다."
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"AI Material Error: {e}")
        return None

# ---------------------------------------------------------
# [NEW] 2단계: 파이썬이 조합 생성 및 API 일괄 검증
# ---------------------------------------------------------
def generate_and_validate_keywords(location, products, tags_input, materials):
    """
    Javascript 로직을 파이썬으로 구현 + API 검증
    """
    if not ADS_API_KEY or not materials: return {}
    
    # 1. 기본 재료 정리
    # location: "용인시 처인구 포곡읍 외 1곳" -> 리스트로 변환
    loc_list = location.replace(" 외 ", " ").replace("곳", "").split()
    # 2글자 미만 지역명 제외 (오류 방지)
    loc_list = [l for l in loc_list if len(l) >= 2] 
    
    main_menu = products.split(",")[0].strip() if products else ""
    tags = [t.replace("#", "").strip() for t in tags_input.split() if t.strip()]
    
    similar_menus = materials.get("similar_menus", [])
    cat_keywords = materials.get("category_keywords", [])
    target_keywords = materials.get("target_keywords", [])
    
    # 2. 조합 생성 (Combinations)
    candidates = [] # {"kwd": "...", "type": "category_expand"}
    
    for loc in loc_list:
        # A. 카테고리 확장 (유사 메뉴)
        for sim in similar_menus:
            candidates.append({"kwd": f"{loc} {sim}", "type": "A_Similar"})
            candidates.append({"kwd": f"{loc} {sim} 맛집", "type": "A_Similar"})
            
        # B. 기본 조합 (업종 카테고리)
        for cat in cat_keywords:
            candidates.append({"kwd": f"{loc} {cat}", "type": "B_Basic"})
            
        # C. 목적/상황 조합 (태그)
        for tag in tags:
            candidates.append({"kwd": f"{loc} {tag}", "type": "C_Purpose"})
            if main_menu:
                candidates.append({"kwd": f"{loc} {tag} {main_menu}", "type": "C_Purpose"})
                
        # D. 타겟 맞춤 (연령/성별 키워드)
        for tgt in target_keywords:
            candidates.append({"kwd": f"{loc} {tgt}", "type": "D_Target"})
            if main_menu:
                candidates.append({"kwd": f"{loc} {tgt} {main_menu}", "type": "D_Target"})

    # 3. API 일괄 조회 (Batch Processing)
    # 중복 제거
    unique_candidates = list({c['kwd']: c for c in candidates}.values())
    
    valid_results = []
    
    # 5개씩 끊어서 요청
    for i in range(0, len(unique_candidates), 5):
        chunk = unique_candidates[i:i+5]
        hint_str = ",".join([c['kwd'].replace(" ", "") for c in chunk])
        
        try:
            headers = get_header("GET", "/keywordstool", ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
            params = {"hintKeywords": hint_str, "showDetail": 1}
            res = requests.get(ADS_BASE_URL + "/keywordstool", params=params, headers=headers)
            
            if res.status_code == 200:
                api_data = res.json().get("keywordList", [])
                for item in api_data:
                    rel_kwd = item['relKeyword']
                    pc = item['monthlyPcQcCnt']
                    mo = item['monthlyMobileQcCnt']
                    if isinstance(pc, str): pc = 0
                    if isinstance(mo, str): mo = 0
                    total = pc + mo
                    
                    # 검색량이 10 이상인 것만 유효
                    if total >= 10:
                        # 원래 요청했던 키워드와 매칭 (API는 연관어도 주므로)
                        clean_rel = rel_kwd.replace(" ", "")
                        matched_type = None
                        
                        for c in chunk:
                            if c['kwd'].replace(" ", "") == clean_rel:
                                matched_type = c['type']
                                break
                        
                        # 정확히 매칭된 것만 저장 (엄격 모드)
                        if matched_type:
                            valid_results.append({
                                "keyword": rel_kwd,
                                "volume": total,
                                "type": matched_type
                            })
            time.sleep(0.05)
        except:
            pass
            
    # 4. 결과 분류 및 정렬
    final_report = {
        "insight": materials.get("insight", ""),
        "main_keywords": [],   # A(유사) + B(기본)
        "detail_keywords": [], # C(목적) + D(타겟)
        "content_ideas": []
    }
    
    # 분류
    for res in valid_results:
        if res['type'] in ['A_Similar', 'B_Basic']:
            final_report['main_keywords'].append(res)
        else:
            final_report['detail_keywords'].append(res)
            
    # 정렬 (검색량 순)
    final_report['main_keywords'].sort(key=lambda x: x['volume'], reverse=True)
    final_report['detail_keywords'].sort(key=lambda x: x['volume'], reverse=True)
    
    # 상위 N개만 자르기
    final_report['main_keywords'] = final_report['main_keywords'][:6]
    final_report['detail_keywords'] = final_report['detail_keywords'][:8]
    
    # 콘텐츠 아이디어 생성 (Python Logic)
    # 1. 상황 중심
    if tags:
        final_report['content_ideas'].append(f"\"{tags[0]} 때, {loc_list[0]}에서 {main_menu} 생각난다면?\"")
    # 2. 비교 큐레이션
    if similar_menus:
        final_report['content_ideas'].append(f"\"{loc_list[0]} {similar_menus[0]} 맛집 BEST 5 vs {main_menu} 리얼 후기\"")
    # 3. 타겟 맞춤
    if target_keywords:
        final_report['content_ideas'].append(f"\"{loc_list[0]} {target_keywords[0]} 데이트 코스, 실패 없는 {main_menu}\"")
        
    return final_report