import time
import hmac
import hashlib
import base64
import requests
import urllib.parse
import os
import json
import logging
import re
from datetime import datetime
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

# ---------------------------------------------------------
# [NEW] 계절 감지
# ---------------------------------------------------------
def get_current_season():
    """현재 계절 감지"""
    month = datetime.now().month
    if month in [3, 4, 5]:
        return "봄"
    elif month in [6, 7, 8]:
        return "여름"
    elif month in [9, 10, 11]:
        return "가을"
    else:
        return "겨울"

def get_seasonal_keywords(category, season):
    """계절별 키워드 맵"""
    seasonal_map = {
        "봄": {
            "한식": ["봄나물", "쑥", "냉이", "봄철", "따뜻한", "봄맞이"],
            "국수/면요리": ["비빔국수", "쟁반국수", "봄철", "시원한"],
            "보양식": ["춘곤증", "피로회복", "활력", "봄보양"],
            "카페/디저트": ["벚꽃", "테라스", "야외", "봄카페", "꽃구경"],
            "default": ["봄", "봄철", "따뜻한"]
        },
        "여름": {
            "한식": ["냉면", "콩국수", "냉국", "시원한", "여름"],
            "국수/면요리": ["냉면", "비빔국수", "콩국수", "열무국수", "시원한"],
            "보양식": ["삼계탕", "보신", "여름보양", "기력회복", "영양"],
            "카페/디저트": ["빙수", "아이스", "시원한", "여름"],
            "default": ["여름", "시원한", "더위"]
        },
        "가을": {
            "한식": ["전", "막걸리", "국밥", "따뜻한", "가을"],
            "국수/면요리": ["칼국수", "따뜻한", "얼큰한", "가을"],
            "보양식": ["보양", "영양", "환절기", "기력"],
            "카페/디저트": ["단풍", "가을", "따뜻한", "가을카페"],
            "default": ["가을", "환절기", "따뜻한"]
        },
        "겨울": {
            "한식": ["국밥", "해장국", "곰탕", "얼큰한", "뜨끈한", "겨울"],
            "국수/면요리": ["칼국수", "뜨끈한", "얼큰한", "해장", "겨울"],
            "보양식": ["보신", "몸보신", "따뜻한", "영양", "겨울보양"],
            "카페/디저트": ["따뜻한", "겨울", "핫초코"],
            "default": ["겨울", "뜨끈한", "따뜻한"]
        }
    }
    
    return seasonal_map.get(season, {}).get(category, seasonal_map[season]["default"])

# ---------------------------------------------------------
# [NEW] 블로그 검색 및 경쟁사 분석
# ---------------------------------------------------------
def get_blog_search_result(keyword):
    """네이버 블로그 검색 API - 개선"""
    if not SEARCH_CLIENT_ID: 
        return {"total": 0, "items": []}
    
    url = f"https://openapi.naver.com/v1/search/blog.json?query={urllib.parse.quote(keyword)}&display=10&sort=sim"
    headers = {
        "X-Naver-Client-Id": SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET
    }
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            return {
                "total": data.get("total", 0), 
                "items": data.get("items", [])
            }
    except Exception as e:
        logger.warning(f"Blog search error: {e}")
    return {"total": 0, "items": []}

def analyze_competitor_blogs(keyword):
    """
    경쟁사 블로그 분석
    - 상위 노출 블로그 분석
    - 포스팅 전략 파악
    """
    blog_data = get_blog_search_result(keyword)
    
    if blog_data['total'] == 0:
        return {
            'total_posts': 0,
            'top_competitors': [],
            'competition_level': 'low',
            'strategy_insight': f"'{keyword}' 키워드는 아직 경쟁이 거의 없습니다. 지금 시작하면 선점 가능합니다!"
        }
    
    top_blogs = []
    for idx, item in enumerate(blog_data['items'][:3], 1):
        # HTML 태그 제거
        title = re.sub(r'<[^>]+>', '', item.get('title', ''))
        description = re.sub(r'<[^>]+>', '', item.get('description', ''))
        
        top_blogs.append({
            'rank': idx,
            'title': title[:50],
            'blogger': item.get('bloggername', '알 수 없음'),
            'date': item.get('postdate', ''),
            'link': item.get('link', '')
        })
    
    # 경쟁 강도 판단
    if blog_data['total'] < 50:
        competition_level = 'low'
        strategy = f"총 {blog_data['total']}개의 포스팅만 있어 경쟁이 약합니다. 블로그 20-30개로 상위 노출 가능!"
    elif blog_data['total'] < 500:
        competition_level = 'medium'
        strategy = f"총 {blog_data['total']}개 포스팅. 중간 경쟁입니다. 꾸준한 블로그 + 인스타 연동으로 3개월 내 상위권 가능!"
    else:
        competition_level = 'high'
        strategy = f"총 {blog_data['total']:,}개로 경쟁이 치열합니다. 롱테일 키워드(예: '{keyword} 후기') 공략 추천!"
    
    return {
        'total_posts': blog_data['total'],
        'top_competitors': top_blogs,
        'competition_level': competition_level,
        'strategy_insight': strategy
    }

# ---------------------------------------------------------
# 키워드 정제 함수
# ---------------------------------------------------------
def sanitize_keyword(keyword):
    """키워드 정제"""
    words = keyword.split()
    seen = set()
    unique_words = []
    for word in words:
        if word == "맛집" and any("맛집" in w for w in unique_words):
            continue
        if word not in seen:
            seen.add(word)
            unique_words.append(word)
    
    cleaned = " ".join(unique_words)
    if len(cleaned) > 30:
        cleaned = cleaned[:30]
    
    return cleaned.strip()

def validate_keyword(keyword):
    """키워드 유효성 검사"""
    if not keyword or len(keyword) < 2:
        return False
    if len(keyword) > 30:
        return False
    if not re.search(r'[가-힣a-zA-Z]', keyword):
        return False
    return True

# ---------------------------------------------------------
# 지역 계층 구조 파싱
# ---------------------------------------------------------
def parse_location_hierarchy(location_input):
    """지역 계층 구조 파싱"""
    cleaned = location_input.replace(" 외 ", " ").replace("곳", "").strip()
    parts = cleaned.split()
    
    result = {
        'si': '',
        'gu': '',
        'dong_list': [],
        'search_locations': []
    }
    
    for part in parts:
        if '시' in part or '군' in part:
            result['si'] = part.replace('시', '').replace('군', '')
            break
    
    for part in parts:
        if '구' in part and '시' not in part:
            result['gu'] = part
            break
    
    for part in parts:
        if any(suffix in part for suffix in ['동', '읍', '면']):
            base = part.rstrip('0123456789').rstrip('동읍면리가')
            if base and len(base) >= 2:
                result['dong_list'].append(base)
            result['dong_list'].append(part)
    
    result['dong_list'] = list(dict.fromkeys(result['dong_list']))
    
    search_locs = []
    if result['si']:
        search_locs.append(result['si'])
    if result['gu']:
        search_locs.append(result['gu'])
        if result['si']:
            search_locs.append(f"{result['si']} {result['gu']}")
    if result['dong_list']:
        main_dong = result['dong_list'][0]
        search_locs.append(main_dong)
        if result['si']:
            search_locs.append(f"{result['si']} {main_dong}")
    
    result['search_locations'] = list(dict.fromkeys(search_locs))[:5]
    logger.info(f"📍 Location: {location_input} → {result['search_locations']}")
    
    return result

# ---------------------------------------------------------
# [ENHANCED] AI 프롬프트 - 계절 + 전략 반영
# ---------------------------------------------------------
def extract_keyword_materials(shop_name, products, category, tags, persona, location):
    """
    전문 마케터 관점의 키워드 재료 추출
    - 모든 메뉴 반영
    - 계절성 반영
    - 타겟층 특성 반영
    """
    if not client:
        logger.warning("OpenAI client not available")
        return None
    
    loc_hierarchy = parse_location_hierarchy(location)
    current_season = get_current_season()
    seasonal_kws = get_seasonal_keywords(category, current_season)
    
    # 메뉴 파싱
    menu_list = [m.strip() for m in products.split(",") if m.strip()]
    main_menu = menu_list[0] if menu_list else products
    all_menus_str = ", ".join(menu_list)
    
    prompt = f"""당신은 15년 경력의 네이버 플레이스 마케팅 전문가입니다.

[가게 정보]
- 위치: {location} (시: {loc_hierarchy['si']}, 구: {loc_hierarchy['gu']})
- 업종: {category}
- 대표 메뉴: {all_menus_str}
  * 메인: {main_menu}
  * 전체: {menu_list}
- 타겟 고객: {persona}
- 가게 특징: {tags}

[계절 정보]
- 현재 계절: {current_season}
- 계절 키워드: {seasonal_kws}

[미션]
지금은 **{current_season}**입니다. 이 계절에 {persona}가 검색할 만한 키워드를 찾으세요.
모든 메뉴를 고려하되, 계절성을 반드시 반영하세요.

[출력 - JSON]
{{
    "actual_menus": [
        // 입력된 실제 메뉴 그대로 (최대 5개)
        // 예: ["닭국수", "닭도리탕", "닭곰탕"]
    ],
    "expanded_menus": [
        // 각 메뉴의 유사어 + 계절 고려 (6개)
        // 겨울: "닭국수" → "닭칼국수", "뜨끈한 국수"
        // 여름: "닭국수" → "비빔국수", "시원한 국수"
    ],
    "seasonal_keywords": [
        // {current_season}에 맞는 키워드 5개
        // 예: 겨울 - ["뜨끈한", "해장", "얼큰한", "따뜻한", "겨울"]
    ],
    "target_intents": [
        // {persona}의 검색 의도 5개 (계절 반영)
        // 예: 겨울 + 30대 남성 → ["점심", "해장", "회식", "술약속", "따뜻한"]
    ],
    "situation_keywords": [
        // {tags} + 계절 조합 5개
        // 예: #해장 + 겨울 → ["해장", "숙취", "얼큰한", "뜨끈한", "아침"]
    ],
    "persona_insight": "{persona}가 {current_season}에 이 가게를 찾는 이유와 검색 패턴",
    "insight": "{all_menus_str} 중 {current_season}에 가장 검색량이 많을 메뉴와 이유"
}}

[중요]
1. 계절성 필수 반영 ({current_season})
2. 모든 메뉴 골고루 포함
3. {persona} 특성 고려
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=1000
        )
        result = json.loads(response.choices[0].message.content)
        result['season'] = current_season  # 계절 정보 추가
        
        logger.info(f"✅ AI Materials ({current_season}):")
        logger.info(f"   - Actual menus: {result.get('actual_menus', [])}")
        logger.info(f"   - Seasonal keywords: {result.get('seasonal_keywords', [])}")
        return result
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return None

# ---------------------------------------------------------
# [REVOLUTIONARY] 전략적 키워드 생성 + 경쟁사 분석
# ---------------------------------------------------------
def generate_and_validate_keywords(location, products, tags_input, materials, persona_text=""):
    """
    전략적 키워드 생성 + 경쟁사 분석
    """
    if not materials:
        return create_empty_report()
    
    # 1. 지역 파싱
    loc_hierarchy = parse_location_hierarchy(location)
    search_locations = loc_hierarchy['search_locations']
    
    if not search_locations:
        return create_empty_report()
    
    # 2. 메뉴 파싱
    menu_list = [m.strip() for m in products.split(",") if m.strip()]
    main_menu = menu_list[0] if menu_list else ""
    tags = [t.replace("#", "").strip() for t in tags_input.split() if t.strip()]
    
    current_season = materials.get('season', get_current_season())
    
    # 3. AI 재료
    actual_menus = materials.get("actual_menus", menu_list[:5])
    expanded_menus = materials.get("expanded_menus", [])
    seasonal_keywords = materials.get("seasonal_keywords", [])
    
    # 모든 메뉴 키워드 결합
    all_menu_keywords = []
    for menu in actual_menus[:5]:
        if menu and len(menu) >= 2:
            all_menu_keywords.append(menu)
    for menu in expanded_menus[:6]:
        if menu and menu not in all_menu_keywords:
            all_menu_keywords.append(menu)
    
    category_words = materials.get("category_words", ["맛집"])[:3]
    target_intents = materials.get("target_intents", ["점심"])[:5]
    situation_keywords = materials.get("situation_keywords", tags)[:5]
    purchase_triggers = materials.get("purchase_triggers", ["추천", "후기"])[:4]
    
    # 4. 키워드 생성
    keyword_pool = {
        'A_Core': [],
        'C_Target': [],
        'D_Situation': []
    }
    
    primary_loc = search_locations[0]
    
    # [Type A] 메인 키워드 - 모든 메뉴 + 계절
    for loc in search_locations[:2]:
        for menu in all_menu_keywords[:8]:
            keyword_pool['A_Core'].append(f"{loc} {menu}")
            keyword_pool['A_Core'].append(f"{loc} {menu} 맛집")
        
        # 계절 키워드
        for seasonal in seasonal_keywords[:3]:
            keyword_pool['A_Core'].append(f"{loc} {seasonal} {main_menu}")
            keyword_pool['A_Core'].append(f"{loc} {seasonal} 맛집")
    
    # [Type C] 타겟 맞춤 - 실제 메뉴 우선
    for intent in target_intents:
        for menu in actual_menus[:3]:
            keyword_pool['C_Target'].append(f"{primary_loc} {intent} {menu}")
        keyword_pool['C_Target'].append(f"{primary_loc} {intent} 맛집")
    
    # [Type D] 상황 + 계절
    for situation in situation_keywords:
        keyword_pool['D_Situation'].append(f"{primary_loc} {situation}")
        keyword_pool['D_Situation'].append(f"{primary_loc} {situation} 맛집")
        for menu in actual_menus[:2]:
            keyword_pool['D_Situation'].append(f"{primary_loc} {situation} {menu}")
    
    # 5. 정제
    for kw_type in keyword_pool:
        cleaned = []
        seen = set()
        for kwd in keyword_pool[kw_type]:
            sanitized = sanitize_keyword(kwd)
            if validate_keyword(sanitized) and sanitized not in seen:
                cleaned.append(sanitized)
                seen.add(sanitized)
        keyword_pool[kw_type] = cleaned
    
    # 6. 쿼터 적용
    selected_candidates = []
    
    for kwd in keyword_pool['A_Core'][:6]:
        selected_candidates.append({"kwd": kwd, "type": "A_Core", "priority": 100})
    for kwd in keyword_pool['C_Target'][:7]:
        selected_candidates.append({"kwd": kwd, "type": "C_Target", "priority": 95})
    for kwd in keyword_pool['D_Situation'][:5]:
        selected_candidates.append({"kwd": kwd, "type": "D_Situation", "priority": 90})
    
    # 7. API 검증
    validated_keywords = []
    if ADS_API_KEY:
        validated_keywords = validate_with_balanced_api(selected_candidates)
    
    # 8. 폴백
    validated_keywords = ensure_minimum_keywords(
        validated_keywords, selected_candidates, search_locations, 
        all_menu_keywords, main_menu
    )
    
    # 9. 경쟁사 분석 (상위 3개 키워드)
    competitor_analysis = []
    top_keywords_for_analysis = []
    
    # 검증된 키워드 중 검색량 높은 순으로 3개
    sorted_keywords = sorted(
        [kw for kw in validated_keywords if kw.get('type') in ['A_Core', 'C_Target']], 
        key=lambda x: x.get('volume', 0), 
        reverse=True
    )
    
    for kw_data in sorted_keywords[:3]:
        keyword = kw_data['keyword']
        comp_analysis = analyze_competitor_blogs(keyword)
        competitor_analysis.append({
            'keyword': keyword,
            'volume': kw_data.get('volume', 0),
            'analysis': comp_analysis
        })
        logger.info(f"🔍 Competitor analysis: {keyword} - {comp_analysis['total_posts']} posts")
    
    # 10. 결과 분류 + 전략 생성
    final_report = classify_keywords_with_strategy(
        validated_keywords, materials, search_locations, 
        all_menu_keywords, tags, main_menu, 
        competitor_analysis, persona_text, current_season
    )
    
    return final_report

# ... (validate_with_balanced_api, ensure_minimum_keywords 함수는 이전과 동일) ...
# 이전 코드에서 가져오기

def validate_with_balanced_api(candidates):
    """타입별 균형 API 호출"""
    validated = []
    api_call_count = 0
    MAX_API_CALLS = 5
    
    type_groups = {
        'A_Core': [c for c in candidates if c['type'] == 'A_Core'],
        'C_Target': [c for c in candidates if c['type'] == 'C_Target'],
        'D_Situation': [c for c in candidates if c['type'] == 'D_Situation']
    }
    
    batch_queue = []
    max_per_type = 2
    for i in range(max_per_type):
        for kw_type in ['A_Core', 'C_Target', 'D_Situation']:
            if i < len(type_groups[kw_type]):
                batch_queue.append(type_groups[kw_type][i])
    
    for kw_type in ['A_Core', 'C_Target', 'D_Situation']:
        remaining = type_groups[kw_type][max_per_type:]
        batch_queue.extend(remaining[:2])
    
    for i in range(0, len(batch_queue), 5):
        if api_call_count >= MAX_API_CALLS:
            break
        
        chunk = batch_queue[i:i+5]
        hint_str = ",".join([c['kwd'].replace(" ", "") for c in chunk])
        
        try:
            headers = get_header("GET", "/keywordstool", ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
            params = {"hintKeywords": hint_str, "showDetail": "1"}
            
            res = requests.get(ADS_BASE_URL + "/keywordstool", params=params, headers=headers, timeout=5)
            
            if res.status_code == 200:
                api_data = res.json().get("keywordList", [])
                
                for item in api_data:
                    rel_kwd = item.get('relKeyword', '')
                    pc = int(item.get('monthlyPcQcCnt', 0)) if str(item.get('monthlyPcQcCnt', 0)).isdigit() else 0
                    mo = int(item.get('monthlyMobileQcCnt', 0)) if str(item.get('monthlyMobileQcCnt', 0)).isdigit() else 0
                    comp_idx = item.get('compIdx', 'low')
                    
                    total_volume = pc + mo
                    
                    if total_volume >= 10:
                        matched = None
                        for c in chunk:
                            c_clean = c['kwd'].replace(" ", "")
                            rel_clean = rel_kwd.replace(" ", "")
                            if c_clean in rel_clean or rel_clean in c_clean:
                                matched = c
                                break
                        
                        if not matched:
                            matched = {"type": "E_Related", "priority": 50}
                        
                        comp_score = {'low': 100, 'medium': 50, 'high': 20}.get(comp_idx, 50)
                        score = (total_volume * 0.5) + comp_score + matched.get('priority', 0)
                        
                        validated.append({
                            "keyword": rel_kwd,
                            "volume": total_volume,
                            "pc": pc,
                            "mobile": mo,
                            "competition": comp_idx,
                            "type": matched['type'],
                            "score": score
                        })
            
            api_call_count += 1
            time.sleep(0.2)
            
        except Exception as e:
            logger.error(f"API Exception: {str(e)}")
            api_call_count += 1
    
    return validated

def ensure_minimum_keywords(validated, all_candidates, locations, menus, main_menu):
    """타입별 최소 개수 보장"""
    type_counts = {}
    for kw in validated:
        kw_type = kw['type']
        type_counts[kw_type] = type_counts.get(kw_type, 0) + 1
    
    min_targets = {
        'A_Core': 4,
        'C_Target': 5,
        'D_Situation': 4
    }
    
    existing_kwds = set([kw['keyword'] for kw in validated])
    
    for kw_type, min_count in min_targets.items():
        current_count = type_counts.get(kw_type, 0)
        shortage = min_count - current_count
        
        if shortage > 0:
            type_candidates = [c for c in all_candidates if c['type'] == kw_type and c['kwd'] not in existing_kwds]
            
            for c in type_candidates[:shortage]:
                base_volume = 200
                if locations[0] in c['kwd']:
                    base_volume = 250
                
                if kw_type == 'C_Target':
                    base_volume = int(base_volume * 0.7)
                elif kw_type == 'D_Situation':
                    base_volume = int(base_volume * 0.5)
                
                validated.append({
                    "keyword": c['kwd'],
                    "volume": base_volume,
                    "pc": int(base_volume * 0.3),
                    "mobile": int(base_volume * 0.7),
                    "competition": "low",
                    "type": kw_type,
                    "score": c['priority'],
                    "is_estimated": True
                })
                existing_kwds.add(c['kwd'])
    
    return validated

# ---------------------------------------------------------
# [NEW] 전략적 분류 함수
# ---------------------------------------------------------
def classify_keywords_with_strategy(validated_keywords, materials, locations, menus, tags, main_menu, competitor_analysis, persona_text, season):
    """키워드 분류 + 전략 생성"""
    
    final_report = {
        "season": season,
        "persona_insight": materials.get("persona_insight", ""),
        "insight": materials.get("insight", ""),
        "main_keywords": [],
        "detail_keywords": [],
        "related_keywords": [],
        "competitor_analysis": competitor_analysis,
        "strategic_recommendations": [],
        "content_ideas": [],
        "action_plan": {}
    }
    
    # 중복 제거
    unique_validated = {}
    for kw in validated_keywords:
        key = kw['keyword']
        if key not in unique_validated or unique_validated[key]['score'] < kw['score']:
            unique_validated[key] = kw
    
    validated_keywords = list(unique_validated.values())
    validated_keywords.sort(key=lambda x: x['score'], reverse=True)
    
    # 분류
    for kw in validated_keywords:
        kw_type = kw['type']
        if kw_type in ['A_Core', 'B_Local']:
            final_report['main_keywords'].append(kw)
        elif kw_type in ['C_Target', 'D_Situation']:
            final_report['detail_keywords'].append(kw)
        elif kw_type == 'E_Related':
            final_report['related_keywords'].append(kw)
    
    final_report['main_keywords'] = final_report['main_keywords'][:10]
    final_report['detail_keywords'] = final_report['detail_keywords'][:12]
    final_report['related_keywords'] = final_report['related_keywords'][:5]
    
    # 전략 추천 생성
    recommendations = []
    
    # 1. 경쟁 강도 기반 전략
    if competitor_analysis:
        top_comp = competitor_analysis[0]
        comp_level = top_comp['analysis']['competition_level']
        
        if comp_level == 'low':
            recommendations.append({
                'priority': 'HIGH',
                'strategy': '블로그 선점 전략',
                'description': f"'{top_comp['keyword']}' 키워드는 경쟁이 약합니다. 블로그 20-30개만으로 상위 노출 가능!",
                'action': f"1개월간 주 2-3회 블로그 포스팅 집중",
                'expected_result': '3개월 내 네이버 검색 1페이지 진입'
            })
        elif comp_level == 'medium':
            recommendations.append({
                'priority': 'MEDIUM',
                'strategy': '복합 채널 전략',
                'description': f"'{top_comp['keyword']}'는 중간 경쟁입니다. 블로그 + 인스타그램 + 리뷰 관리 병행 필요",
                'action': '블로그(주 2회) + 인스타(주 5회) + 고객 리뷰 유도',
                'expected_result': '4-6개월 내 상위 5위권 진입'
            })
        else:
            recommendations.append({
                'priority': 'STRATEGIC',
                'strategy': '롱테일 키워드 공략',
                'description': f"'{top_comp['keyword']}'는 경쟁이 치열합니다. 세부 키워드로 우회 공략 추천",
                'action': f"'{final_report['detail_keywords'][0]['keyword']}' 같은 롱테일 키워드 집중",
                'expected_result': '2-3개월 내 틈새 키워드 상위 노출'
            })
    
    # 2. 계절 기반 전략
    recommendations.append({
        'priority': 'SEASONAL',
        'strategy': f'{season} 시즌 마케팅',
        'description': f"지금은 {season}입니다. 계절 키워드를 활용한 콘텐츠 제작이 효과적입니다.",
        'action': f"{season} 관련 블로그/인스타 콘텐츠 집중 (예: '{season} {main_menu}')",
        'expected_result': f'{season} 기간(3개월) 동안 유입 30% 증가 예상'
    })
    
    # 3. 타겟층 기반 전략
    if persona_text:
        recommendations.append({
            'priority': 'TARGET',
            'strategy': f'{persona_text} 맞춤 콘텐츠',
            'description': materials.get('persona_insight', '타겟 고객의 검색 패턴을 반영한 전략'),
            'action': f"타겟층이 많이 검색하는 '{final_report['detail_keywords'][0]['keyword'] if final_report['detail_keywords'] else main_menu}' 키워드 집중",
            'expected_result': '전환율 20% 향상 기대'
        })
    
    final_report['strategic_recommendations'] = recommendations
    
    # 실행 계획
    total_keywords = len(final_report['main_keywords']) + len(final_report['detail_keywords'])
    
    final_report['action_plan'] = {
        'month_1': {
            'focus': '기반 구축',
            'actions': [
                f"블로그 포스팅 8-10개 작성 (메인 키워드 {len(final_report['main_keywords'][:3])}개 포함)",
                "네이버 플레이스 정보 최적화",
                "고객 리뷰 5개 이상 확보"
            ],
            'expected': '네이버 검색 노출 시작'
        },
        'month_2': {
            'focus': '확장 및 강화',
            'actions': [
                "블로그 포스팅 추가 10개 (세부 키워드 포함)",
                "인스타그램 연동 시작 (주 3-5회)",
                "기존 포스팅 업데이트"
            ],
            'expected': '검색 순위 10-20위권 진입'
        },
        'month_3': {
            'focus': '최적화 및 유지',
            'actions': [
                "상위 노출 키워드 집중 관리",
                "리뷰 관리 및 답글",
                "계절별 콘텐츠 업데이트"
            ],
            'expected': '목표 키워드 상위 5-10위 안정화'
        }
    }
    
    # 콘텐츠 아이디어 (구체적으로)
    ideas = []
    
    if final_report['main_keywords']:
        top_kw = final_report['main_keywords'][0]
        ideas.append({
            'type': 'SEO 블로그',
            'title': f"\"{top_kw['keyword']} BEST 5 - 현지인이 추천하는 진짜 맛집\"",
            'reason': f"월 {top_kw['volume']:,}건 검색되는 메인 키워드 공략",
            'content_guide': f"1. 우리 가게 소개 (사진 5장+), 2. 메뉴 리뷰, 3. 가격/주차 정보, 4. 방문 후기"
        })
    
    if final_report['detail_keywords'] and tags:
        detail_kw = final_report['detail_keywords'][0]
        ideas.append({
            'type': '상황 공감 콘텐츠',
            'title': f"\"{tags[0]} 때 생각나는 {locations[0]} {main_menu}, 여기 가세요\"",
            'reason': f"특정 상황 검색 고객 전환율 높음",
            'content_guide': f"1. 상황 공감 스토리텔링, 2. 우리 가게가 딱인 이유, 3. 실제 방문 사진, 4. 꿀팁"
        })
    
    if season:
        ideas.append({
            'type': '계절 콘텐츠',
            'title': f"\"{season}에 더 맛있는 {main_menu}, {locations[0]}에서 먹어야 하는 이유\"",
            'reason': f"{season} 시즌 특수 활용",
            'content_guide': f"1. {season} 특성과 메뉴 연결, 2. 계절 한정 메뉴 강조, 3. 분위기 사진"
        })
    
    if competitor_analysis:
        comp = competitor_analysis[0]
        ideas.append({
            'type': '차별화 콘텐츠',
            'title': f"\"{comp['keyword']} 숨은 맛집 - 블로그에 안 나온 진짜 맛집\"",
            'reason': f"경쟁 키워드 우회 공략",
            'content_guide': "1. '숨은 맛집' 컨셉, 2. 다른 곳과 차별점, 3. 단골 인터뷰"
        })
    
    final_report['content_ideas'] = ideas[:4]
    
    return final_report

def create_empty_report():
    """빈 리포트"""
    return {
        "season": get_current_season(),
        "insight": "분석 데이터 부족",
        "main_keywords": [],
        "detail_keywords": [],
        "related_keywords": [],
        "competitor_analysis": [],
        "strategic_recommendations": [],
        "content_ideas": [],
        "action_plan": {}
    }