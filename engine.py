"""
네이버 쇼핑 URL 파싱 + 순위 추적 엔진 (가격비교 카탈로그 대응 버전)

[핵심 개념]
네이버 쇼핑에는 2가지 상품 구조가 존재:

① 일반 스마트스토어 상품 (productType 2, 3)
   URL: smartstore.naver.com/store/products/[스마트스토어상품ID]
   API productId = 스마트스토어 상품 고유번호

② 가격비교(카탈로그) 상품 (productType 1) ← 상위권 상품 대부분 해당
   URL: search.shopping.naver.com/catalog/[카탈로그ID]
   API productId = 카탈로그 번호 (스마트스토어 ID와 완전히 다름!)

따라서 스마트스토어 상품 URL을 입력해도 가격비교 카탈로그로
묶여있으면 카탈로그 ID로 검색해야 발견 가능.

[3중 매칭 전략]
1순위: catalog_id 직접 매칭 (가장 정확)
2순위: product_id 직접 매칭 (일반 상품)
3순위: mall_name 부분 일치 (fallback)
"""
import re
import time
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

NAVER_SHOP_API = "https://openapi.naver.com/v1/search/shop.json"


# ─────────────────────────────────────────
# URL 파싱: productId + catalogId 동시 추출
# ─────────────────────────────────────────
def parse_product_info(url: str) -> dict:
    """
    URL에서 product_id, catalog_id, url_product_id 추출

    [중요] 네이버 쇼핑 API의 productId 구조:
      - 스마트스토어 URL의 products/{숫자} ≠ API의 productId (완전히 다른 값!)
      - API의 link 필드에는 스마트스토어 URL이 그대로 들어있음
      - 따라서 URL 내 숫자(url_product_id)로 link 필드를 매칭해야 함

    Returns: {
      "product_id": str|None,       # URL에서 뽑은 숫자 (매칭 키로 사용)
      "catalog_id": str|None,       # 가격비교 카탈로그 ID
      "url_product_id": str|None,   # 스마트스토어 products/{숫자} (link 매칭용)
      "url_type": str
    }
    """
    url = url.strip()
    result = {"product_id": None, "catalog_id": None, "url_product_id": None, "url_type": "unknown"}

    # 순수 숫자 직접 입력
    if re.fullmatch(r'\d{8,}', url):
        result["product_id"] = url
        result["url_type"] = "direct_id"
        return result

    # ① 가격비교 카탈로그 URL → catalog_id
    m = re.search(r'shopping\.naver\.com/catalog/(\d+)', url)
    if m:
        result["catalog_id"] = m.group(1)
        result["product_id"] = m.group(1)
        result["url_type"] = "catalog"
        return result

    # ② 스마트스토어 URL → url_product_id (link 매칭용)
    m = re.search(r'smartstore\.naver\.com/[^/?#]+/products/(\d+)', url)
    if m:
        uid = m.group(1)
        result["product_id"] = uid
        result["url_product_id"] = uid   # ★ link 필드 매칭에 사용
        result["url_type"] = "smartstore"
        return result

    # ③ nv_mid 파라미터
    m = re.search(r'[?&]nv_mid=(\d+)', url)
    if m:
        result["product_id"] = m.group(1)
        result["url_type"] = "nv_mid"
        return result

    # ④ URL 끝 숫자
    m = re.search(r'/(\d{8,})(?:[?/#]|$)', url)
    if m:
        result["product_id"] = m.group(1)
        result["url_type"] = "url_number"
        return result

    return result


def parse_product_id(url: str) -> str | None:
    """기존 호환성 유지용"""
    info = parse_product_info(url)
    return info.get("product_id")


# ─────────────────────────────────────────
# 네이버 쇼핑 API 호출
# ─────────────────────────────────────────
def search_shopping(client_id: str, client_secret: str,
                    query: str, start: int = 1, display: int = 100) -> dict | None:
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": "sim",
        # 가격비교 포함: used/rental만 제외 (cbshop=해외직구 포함 여부는 광고주 설정에 따라)
        "exclude": "used:rental",
    }
    try:
        resp = requests.get(NAVER_SHOP_API, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        code = e.response.status_code if e.response else 0
        logger.error(f"API HTTP {code} 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"API 호출 오류: {e}")
        return None


def clean_title(t: str) -> str:
    return re.sub(r'<[^>]+>', '', t or '')


def normalize_name(s: str) -> str:
    """공백/특수문자 제거 소문자 정규화 (mallName 비교용)"""
    return re.sub(r'[\s\-_·•]', '', (s or '').lower())


# ─────────────────────────────────────────
# 3중 매칭 로직
# ─────────────────────────────────────────
def is_match(item: dict, product: dict) -> bool:
    """
    API 응답 item이 추적 대상 product인지 4단계로 확인

    [네이버 쇼핑 API 상품 ID 구조 주의]
    - API productId ≠ 스마트스토어 URL의 products/{숫자}
    - 스마트스토어 상품은 API의 'link' 필드에 원본 URL이 포함됨
    - 따라서 url_product_id로 link 필드를 검색해야 정확히 찾을 수 있음

    product 구조:
    {
      "product_id": "...",        # URL에서 파싱된 숫자
      "catalog_id": "...",        # 가격비교 카탈로그 ID
      "url_product_id": "...",    # 스마트스토어 products/{숫자} ← link 매칭용
      "mall_name": "...",         # 스토어명 (fallback)
    }
    """
    api_pid  = str(item.get("productId", "")).strip()
    api_link = item.get("link", "")
    api_mall = item.get("mallName", "")

    # ──── 1순위: catalog_id 직접 매칭 (가격비교 카탈로그) ────
    catalog_id = str(product.get("catalog_id") or "").strip()
    if catalog_id and api_pid == catalog_id:
        logger.debug(f"  [1순위 catalog_id 매칭] {api_pid}")
        return True

    # ──── 2순위: url_product_id → link 필드 포함 매칭 ────
    # 스마트스토어 URL의 products/{숫자}가 API link에 들어있는지 확인
    # 예) url_product_id=5835104592, api_link=https://smartstore.naver.com/main/products/5835104592
    url_pid = str(product.get("url_product_id") or "").strip()
    if url_pid and url_pid in api_link:
        logger.debug(f"  [2순위 link 포함 매칭] url_pid={url_pid} in link={api_link}")
        return True

    # ──── 3순위: product_id 직접 매칭 (API productId와 동일한 경우) ────
    product_id = str(product.get("product_id") or "").strip()
    if product_id and api_pid == product_id:
        logger.debug(f"  [3순위 product_id 직접 매칭] {api_pid}")
        return True

    # ──── 4순위: mall_name 부분 일치 (최후 fallback) ────
    mall_name_target = product.get("mall_name", "").strip()
    if mall_name_target:
        t_norm = normalize_name(mall_name_target)
        a_norm = normalize_name(api_mall)
        if t_norm and a_norm and (t_norm in a_norm or a_norm in t_norm):
            logger.debug(f"  [4순위 mall_name 매칭] {api_mall} ≈ {mall_name_target}")
            return True

    return False


# ─────────────────────────────────────────
# 순위 탐색 (단일 키워드 × 단일 상품)
# ─────────────────────────────────────────
def find_rank(client_id: str, client_secret: str,
              keyword: str, target_product_id: str,
              max_pages: int = 10,
              catalog_id: str = None,
              url_product_id: str = None,
              mall_name: str = None) -> dict:
    """
    특정 키워드에서 특정 상품의 순위를 4중 매칭으로 탐색

    Args:
        target_product_id: URL에서 추출한 숫자 ID
        catalog_id: 가격비교 카탈로그 ID
        url_product_id: 스마트스토어 products/{숫자} → API link 필드 매칭용 ★
        mall_name: 스토어명 (4순위 fallback)
    """
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    product = {
        "product_id": str(target_product_id).strip(),
        "catalog_id": str(catalog_id).strip() if catalog_id else None,
        "url_product_id": str(url_product_id).strip() if url_product_id else None,
        "mall_name": mall_name or "",
    }

    logger.info(f"  탐색: '{keyword}' | PID={product['product_id']} | CatalogID={product['catalog_id']} | UrlPID={product['url_product_id']} | Mall={product['mall_name']}")

    for page in range(max_pages):
        start = page * 100 + 1
        data = search_shopping(client_id, client_secret, keyword, start=start, display=100)
        if not data:
            break

        items = data.get("items", [])
        if not items:
            break

        for idx, item in enumerate(items):
            if is_match(item, product):
                rank = start + idx
                p_type = item.get("productType", 0)
                type_label = "가격비교" if p_type == 1 else "일반상품"
                logger.info(f"  ✅ 발견! 순위={rank}위 | 타입={type_label}(productType={p_type}) | mallName={item.get('mallName','')} | apiId={item.get('productId','')}")
                return {
                    "rank": rank,
                    "product_name": clean_title(item.get("title", "")),
                    "mall_name": item.get("mallName", ""),
                    "lprice": int(item.get("lprice", 0) or 0),
                    "product_type": p_type,
                    "matched_id": str(item.get("productId", "")),
                    "checked_at": checked_at,
                    "found": True,
                }

        time.sleep(0.12)

    logger.info(f"  ❌ 미발견: '{keyword}' | {max_pages * 100}위 내 없음")
    return {
        "rank": None,
        "product_name": "",
        "mall_name": "",
        "lprice": 0,
        "product_type": None,
        "matched_id": None,
        "checked_at": checked_at,
        "found": False,
    }


# ─────────────────────────────────────────
# 광고주 전체 추적
# ─────────────────────────────────────────
def track_client(client_id_naver: str, client_secret: str,
                 client_db_id: int, products: list, keywords: list,
                 max_pages: int = 10) -> list:
    """
    광고주의 모든 (상품 × 키워드) 조합 순위 추적

    products: [{"product_id": "...", "catalog_id": "...", "mall_name": "...", "product_name": "..."}]
    """
    results = []
    total = len(products) * len(keywords)
    done = 0

    for product in products:
        for kw in keywords:
            done += 1
            logger.info(f"[{done}/{total}] '{kw}' × {product.get('product_name', product['product_id'])}")
            result = find_rank(
                client_id_naver, client_secret,
                keyword=kw,
                target_product_id=product["product_id"],
                catalog_id=product.get("catalog_id"),
                url_product_id=product.get("url_product_id"),
                mall_name=product.get("mall_name", ""),
                max_pages=max_pages,
            )
            result.update({
                "client_id": client_db_id,
                "product_id": product["product_id"],
                "product_name": result["product_name"] or product.get("product_name", ""),
                "keyword": kw,
            })
            results.append(result)
            time.sleep(0.1)

    return results
