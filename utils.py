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
    """네이버 블로그 검색 API"""
    if not SEARCH_CLIENT_ID: 
        return {"total": 0, "items": []}
    
    url = f"https://openapi.naver.com/v1/search/blog.json?query={urllib.parse.quote(keyword)}&display=3&sort=sim"
    headers = {
        "X-Naver-Client-Id": SEARCH_CLIENT_ID,
        "X-Naver-Client-Secret": SEARCH_CLIENT_SECRET
    }
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            return {"total": data.get("total", 0), "items": data.get("items", [])}
    except Exception as e:
        logger.warning(f"Blog search error: {e}")
    return {"total": 0, "items": []}

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
# [ENHANCED] AI 프롬프트 - 전문 마케터 관점
# ---------------------------------------------------------
def extract_keyword_materials(shop_name, products, category, tags, persona, location):
    """전문 마케터 관점의 키워드 재료 추출"""
    if not client:
        logger.warning("OpenAI client not available")
        return None
    
    loc_hierarchy = parse_location_hierarchy(location)
    
    prompt = f"""당신은 15년 경력의 네이버 플레이스 마케팅 전문가입니다.

[가게 정보]
- 위치: {location} (시: {loc_hierarchy['si']}, 구: {loc_hierarchy['gu']})
- 업종: {category}
- 메뉴: {products}
- 타겟 고객: {persona}
- 가게 특징: {tags}

[미션]
이 가게가 네이버 검색에서 상위 노출되도록 키워드 전략을 짜세요.

[출력 형식 - JSON]
{{
    "core_menus": [
        // {products}보다 검색량 많은 대중적 메뉴명 4개
        // 예: "닭국수" → ["칼국수", "국수", "탕", "면요리"]
    ],
    "category_words": [
        // {category} 대표 키워드 3개
        // 예: ["한식", "한식당", "밥집"]
    ],
    "target_intents": [
        // {persona}의 검색 의도 5개 (전문가 분석)
        // 예: 30대 남성 → ["점심", "회식", "저녁", "술약속", "가성비"]
        // 예: 20대 여성 → ["데이트", "브런치", "분위기", "인스타", "카페"]
    ],
    "situation_keywords": [
        // {tags} 기반 상황별 키워드 5개
        // 예: #해장 → ["해장", "술깨는", "숙취", "아침", "얼큰"]
        // 예: #비오는날 → ["비오는날", "우중", "비", "날씨", "흐린날"]
    ],
    "purchase_triggers": [
        // 구매 전환율 높은 키워드 4개 (전문가 노하우)
        // 예: ["추천", "후기", "맛집", "가까운"]
    ],
    "insight": "{products.split(',')[0]}보다 core_menus[0]를 검색하는 이유"
}}

[중요]
1. 모든 키워드는 단일 명사만
2. 실제 검색될 만한 단어만
3. 중복 금지
4. 지역 특성 고려
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=800
        )
        result = json.loads(response.choices[0].message.content)
        logger.info(f"✅ AI Materials: {json.dumps(result, ensure_ascii=False)}")
        return result
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")
        return None

# ---------------------------------------------------------
# [REVOLUTIONARY] 타입별 균형 키워드 생성
# ---------------------------------------------------------
def generate_and_validate_keywords(location, products, tags_input, materials):
    """
    전문가 수준의 키워드 생성
    - 타입별 쿼터 시스템
    - 균형잡힌 API 호출
    """
    if not materials:
        logger.warning("Materials not available")
        return create_empty_report()
    
    # 1. 지역 계층 파싱
    loc_hierarchy = parse_location_hierarchy(location)
    search_locations = loc_hierarchy['search_locations']
    
    if not search_locations:
        return create_empty_report()
    
    main_menu = products.split(",")[0].strip() if products else ""
    all_menus = [m.strip() for m in products.split(",") if m.strip()][:3]
    tags = [t.replace("#", "").strip() for t in tags_input.split() if t.strip()]
    
    # 2. AI 재료
    core_menus = materials.get("core_menus", [main_menu])[:4]
    category_words = materials.get("category_words", ["맛집"])[:3]
    target_intents = materials.get("target_intents", ["점심", "저녁"])[:5]
    situation_keywords = materials.get("situation_keywords", tags)[:5]
    purchase_triggers = materials.get("purchase_triggers", ["추천", "후기"])[:4]
    
    # 3. 타입별 키워드 생성 (쿼터 시스템)
    keyword_pool = {
        'A_Core': [],      # 메인 타겟 (검색량 높음)
        'C_Target': [],    # 타겟 맞춤 (전환율 높음)
        'D_Situation': []  # 상황 키워드 (롱테일)
    }
    
    # [Type A] 메인 타겟 키워드 생성
    for loc in search_locations[:2]:
        for menu in core_menus[:3]:
            keyword_pool['A_Core'].append(f"{loc} {menu}")
            keyword_pool['A_Core'].append(f"{loc} {menu} 맛집")
        
        for cat in category_words:
            if "맛집" not in cat:
                keyword_pool['A_Core'].append(f"{loc} {cat}")
                keyword_pool['A_Core'].append(f"{loc} {cat} 맛집")
            else:
                keyword_pool['A_Core'].append(f"{loc} {cat}")
    
    # [Type C] 타겟 맞춤 키워드 생성 (전문가 노하우)
    primary_loc = search_locations[0]
    
    for intent in target_intents:
        # 의도 + 메뉴
        for menu in core_menus[:2]:
            keyword_pool['C_Target'].append(f"{primary_loc} {intent} {menu}")
        
        # 의도 + 카테고리
        keyword_pool['C_Target'].append(f"{primary_loc} {intent} {category_words[0]}")
        keyword_pool['C_Target'].append(f"{primary_loc} {intent} 맛집")
    
    # 구매 전환 키워드
    for trigger in purchase_triggers:
        keyword_pool['C_Target'].append(f"{primary_loc} {main_menu} {trigger}")
        keyword_pool['C_Target'].append(f"{primary_loc} {category_words[0]} {trigger}")
    
    # [Type D] 상황 키워드 생성 (롱테일 전략)
    for situation in situation_keywords:
        # 상황 단독
        keyword_pool['D_Situation'].append(f"{primary_loc} {situation}")
        keyword_pool['D_Situation'].append(f"{primary_loc} {situation} 맛집")
        
        # 상황 + 메뉴
        if main_menu:
            keyword_pool['D_Situation'].append(f"{primary_loc} {situation} {main_menu}")
        
        # 상황 + 카테고리
        keyword_pool['D_Situation'].append(f"{primary_loc} {situation} {category_words[0]}")
    
    # 태그 기반 추가
    for tag in tags[:3]:
        if tag not in situation_keywords:
            keyword_pool['D_Situation'].append(f"{primary_loc} {tag}")
            keyword_pool['D_Situation'].append(f"{primary_loc} {tag} 맛집")
    
    # 4. 키워드 정제 (타입별)
    for kw_type in keyword_pool:
        cleaned = []
        seen = set()
        
        for kwd in keyword_pool[kw_type]:
            sanitized = sanitize_keyword(kwd)
            if validate_keyword(sanitized) and sanitized not in seen:
                cleaned.append(sanitized)
                seen.add(sanitized)
        
        keyword_pool[kw_type] = cleaned
    
    # 5. 타입별 쿼터 적용 (균형잡힌 선택)
    selected_candidates = []
    
    # A_Core: 5개
    for kwd in keyword_pool['A_Core'][:5]:
        selected_candidates.append({
            "kwd": kwd,
            "type": "A_Core",
            "priority": 100
        })
    
    # C_Target: 6개 (중요!)
    for kwd in keyword_pool['C_Target'][:6]:
        selected_candidates.append({
            "kwd": kwd,
            "type": "C_Target",
            "priority": 95  # 우선순위 상향!
        })
    
    # D_Situation: 5개
    for kwd in keyword_pool['D_Situation'][:5]:
        selected_candidates.append({
            "kwd": kwd,
            "type": "D_Situation",
            "priority": 90  # 우선순위 상향!
        })
    
    logger.info(f"🎯 Balanced Selection: A_Core={len([c for c in selected_candidates if c['type']=='A_Core'])}, C_Target={len([c for c in selected_candidates if c['type']=='C_Target'])}, D_Situation={len([c for c in selected_candidates if c['type']=='D_Situation'])}")
    
    for i, c in enumerate(selected_candidates[:10], 1):
        logger.info(f"   {i}. [{c['type']}] {c['kwd']}")
    
    # 6. API 검증 (타입별 균형 유지)
    validated_keywords = []
    
    if ADS_API_KEY:
        validated_keywords = validate_with_balanced_api(selected_candidates)
    
    # 7. 폴백 전략 (타입별 최소 보장)
    validated_keywords = ensure_minimum_keywords(
        validated_keywords,
        selected_candidates,
        search_locations,
        core_menus,
        main_menu
    )
    
    # 8. 결과 분류
    final_report = classify_keywords(
        validated_keywords,
        materials,
        search_locations,
        core_menus,
        tags,
        main_menu
    )
    
    return final_report

def validate_with_balanced_api(candidates):
    """
    타입별 균형을 유지하면서 API 호출
    각 타입에서 최소 1-2개씩 검증
    """
    validated = []
    api_call_count = 0
    MAX_API_CALLS = 5  # 3→5로 증가
    
    # 타입별 그룹화
    type_groups = {
        'A_Core': [c for c in candidates if c['type'] == 'A_Core'],
        'C_Target': [c for c in candidates if c['type'] == 'C_Target'],
        'D_Situation': [c for c in candidates if c['type'] == 'D_Situation']
    }
    
    # 타입별로 번갈아가며 API 호출
    batch_queue = []
    
    # 라운드 로빈 방식으로 배치 구성
    max_per_type = 2  # 각 타입에서 2개씩
    for i in range(max_per_type):
        for kw_type in ['A_Core', 'C_Target', 'D_Situation']:
            if i < len(type_groups[kw_type]):
                batch_queue.append(type_groups[kw_type][i])
    
    # 남은 것들 추가
    for kw_type in ['A_Core', 'C_Target', 'D_Situation']:
        remaining = type_groups[kw_type][max_per_type:]
        batch_queue.extend(remaining[:2])  # 각각 2개씩 더
    
    logger.info(f"🔄 API Queue: {len(batch_queue)} candidates ({len([c for c in batch_queue if c['type']=='A_Core'])} Core, {len([c for c in batch_queue if c['type']=='C_Target'])} Target, {len([c for c in batch_queue if c['type']=='D_Situation'])} Situation)")
    
    # API 호출
    for i in range(0, len(batch_queue), 5):
        if api_call_count >= MAX_API_CALLS:
            break
        
        chunk = batch_queue[i:i+5]
        hint_str = ",".join([c['kwd'].replace(" ", "") for c in chunk])
        
        try:
            headers = get_header("GET", "/keywordstool", ADS_API_KEY, ADS_SECRET_KEY, CUSTOMER_ID)
            params = {"hintKeywords": hint_str, "showDetail": "1"}
            
            logger.info(f"📡 API Call #{api_call_count + 1}: {[(c['type'], c['kwd']) for c in chunk]}")
            res = requests.get(ADS_BASE_URL + "/keywordstool", params=params, headers=headers, timeout=5)
            
            if res.status_code == 200:
                api_data = res.json().get("keywordList", [])
                logger.info(f"   ✅ Success: {len(api_data)} results")
                
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
                        logger.info(f"      → [{matched['type']}] {rel_kwd}: {total_volume:,}")
            else:
                try:
                    error_body = res.json()
                    logger.error(f"   ❌ API Error {res.status_code}: {error_body}")
                except:
                    logger.error(f"   ❌ API Error {res.status_code}")
            
            api_call_count += 1
            time.sleep(0.2)
            
        except Exception as e:
            logger.error(f"❌ API Exception: {str(e)}")
            api_call_count += 1
    
    # 타입별 검증 개수 확인
    type_counts = {}
    for kw in validated:
        kw_type = kw['type']
        type_counts[kw_type] = type_counts.get(kw_type, 0) + 1
    
    logger.info(f"📊 API Validation: Total={len(validated)}, {type_counts}")
    
    return validated

def ensure_minimum_keywords(validated, all_candidates, locations, menus, main_menu):
    """
    타입별 최소 개수 보장
    - A_Core: 최소 4개
    - C_Target: 최소 5개
    - D_Situation: 최소 4개
    """
    type_counts = {}
    for kw in validated:
        kw_type = kw['type']
        type_counts[kw_type] = type_counts.get(kw_type, 0) + 1
    
    logger.info(f"🔍 Current counts: {type_counts}")
    
    # 최소 목표
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
            logger.info(f"⚠️ {kw_type} shortage: {shortage}, adding fallback")
            
            # 해당 타입의 후보 중 아직 검증 안된 것
            type_candidates = [c for c in all_candidates if c['type'] == kw_type and c['kwd'] not in existing_kwds]
            
            for c in type_candidates[:shortage]:
                # 지역 크기에 따른 추정 검색량
                base_volume = 200
                if locations[0] in c['kwd']:
                    base_volume = 250
                if len(locations) > 1 and locations[1] in c['kwd']:
                    base_volume = 150
                
                # 타입별 추정 검색량 조정
                if kw_type == 'C_Target':
                    base_volume = int(base_volume * 0.7)  # 타겟 키워드는 약간 낮음
                elif kw_type == 'D_Situation':
                    base_volume = int(base_volume * 0.5)  # 상황 키워드는 더 낮음
                
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
                logger.info(f"   + [{kw_type}] {c['kwd']} (~{base_volume})")
    
    return validated

def classify_keywords(validated_keywords, materials, locations, menus, tags, main_menu):
    """키워드 분류 및 최종 리포트"""
    final_report = {
        "insight": materials.get("insight", "전문가 분석 완료"),
        "main_keywords": [],
        "detail_keywords": [],
        "related_keywords": [],
        "content_ideas": [],
        "debug_info": {
            "total_validated": len(validated_keywords),
            "locations_used": locations
        }
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
    
    # 개수 제한
    final_report['main_keywords'] = final_report['main_keywords'][:10]
    final_report['detail_keywords'] = final_report['detail_keywords'][:12]  # 세부 키워드 개수 증가
    final_report['related_keywords'] = final_report['related_keywords'][:5]
    
    # 전문가 수준의 콘텐츠 아이디어
    ideas = []
    
    if final_report['main_keywords']:
        top_kw = final_report['main_keywords'][0]
        vol_text = f"{top_kw['volume']:,}건" if not top_kw.get('is_estimated') else f"~{top_kw['volume']:,}건"
        ideas.append(
            f"📊 메인 SEO 블로그: \"{top_kw['keyword']} 베스트 5 - 현지인 추천\" (월 {vol_text}, 높은 유입)"
        )
    
    if final_report['detail_keywords']:
        detail_kw = final_report['detail_keywords'][0]
        vol_text = f"{detail_kw['volume']:,}건" if not detail_kw.get('is_estimated') else f"~{detail_kw['volume']:,}건"
        ideas.append(
            f"🎯 전환 최적화 콘텐츠: \"{detail_kw['keyword']} 솔직 후기\" (월 {vol_text}, 높은 전환율)"
        )
    
    if tags and menus:
        ideas.append(
            f"💡 상황 공감 콘텐츠: \"{tags[0]} 때는 {locations[0]} {menus[0]}가 최고인 이유\" (바이럴 유도)"
        )
    
    if final_report['detail_keywords'] and len(final_report['detail_keywords']) > 1:
        detail_kw2 = final_report['detail_keywords'][1]
        ideas.append(
            f"🔥 타겟 맞춤 콘텐츠: \"{detail_kw2['keyword']} 가기 전 꼭 알아야 할 것\" (재방문 유도)"
        )
    
    final_report['content_ideas'] = ideas
    
    logger.info(f"📊 Final Report: Main={len(final_report['main_keywords'])}, Detail={len(final_report['detail_keywords'])}, Related={len(final_report['related_keywords'])}")
    
    return final_report

def create_empty_report():
    """빈 리포트"""
    return {
        "insight": "키워드 분석 데이터 부족",
        "main_keywords": [],
        "detail_keywords": [],
        "related_keywords": [],
        "content_ideas": [],
        "debug_info": {}
    }