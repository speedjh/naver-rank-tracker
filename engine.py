"""
네이버 쇼핑 URL 파싱 + 순위 추적 엔진
"""
import re
import time
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

NAVER_SHOP_API = "https://openapi.naver.com/v1/search/shop.json"


# ─────────────────────────────────────────
# URL → productId 파싱
# ─────────────────────────────────────────
def parse_product_id(url: str) -> str | None:
    """
    네이버 쇼핑 상품 URL에서 productId 추출

    지원 URL 패턴:
      - https://smartstore.naver.com/{store}/products/{id}
      - https://search.shopping.naver.com/catalog/{id}
      - https://search.shopping.naver.com/search/all?...&nv_mid={id}...
      - https://shopping.naver.com/...?nv_mid={id}
      - 순수 숫자만 입력해도 OK
    """
    url = url.strip()

    # 1. 순수 숫자 (productId 직접 입력)
    if re.fullmatch(r'\d{8,}', url):
        return url

    # 2. smartstore.naver.com/store/products/{id}
    m = re.search(r'smartstore\.naver\.com/[^/]+/products/(\d+)', url)
    if m:
        return m.group(1)

    # 3. search.shopping.naver.com/catalog/{id}
    m = re.search(r'shopping\.naver\.com/catalog/(\d+)', url)
    if m:
        return m.group(1)

    # 4. nv_mid 쿼리 파라미터
    m = re.search(r'[?&]nv_mid=(\d+)', url)
    if m:
        return m.group(1)

    # 5. URL 끝의 숫자 (일반적인 패턴)
    m = re.search(r'/(\d{8,})(?:[?/#]|$)', url)
    if m:
        return m.group(1)

    return None


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


# ─────────────────────────────────────────
# 순위 탐색 (단일 키워드 × 단일 상품)
# ─────────────────────────────────────────
def find_rank(client_id: str, client_secret: str,
              keyword: str, target_product_id: str,
              max_pages: int = 10) -> dict:
    """
    특정 키워드에서 특정 productId의 순위를 찾아 반환

    Returns:
        {
          "rank": int or None,
          "product_name": str,
          "mall_name": str,
          "lprice": int,
          "checked_at": str
        }
    """
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_id = str(target_product_id).strip()

    for page in range(max_pages):
        start = page * 100 + 1
        data = search_shopping(client_id, client_secret, keyword, start=start, display=100)
        if not data:
            break

        items = data.get("items", [])
        if not items:
            break

        for idx, item in enumerate(items):
            if str(item.get("productId", "")) == target_id:
                rank = start + idx
                return {
                    "rank": rank,
                    "product_name": clean_title(item.get("title", "")),
                    "mall_name": item.get("mallName", ""),
                    "lprice": int(item.get("lprice", 0) or 0),
                    "checked_at": checked_at,
                    "found": True,
                }

        time.sleep(0.12)  # API 호출 간격

    # 미발견
    return {
        "rank": None,
        "product_name": "",
        "mall_name": "",
        "lprice": 0,
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

    products: [{"product_id": "...", "product_name": "..."}]
    keywords: ["키워드1", "키워드2", ...]

    Returns: list of rank result dicts
    """
    results = []
    total = len(products) * len(keywords)
    done = 0

    for product in products:
        for kw in keywords:
            done += 1
            logger.info(f"[{done}/{total}] '{kw}' × 상품 {product['product_id']}")
            result = find_rank(
                client_id_naver, client_secret,
                keyword=kw,
                target_product_id=product["product_id"],
                max_pages=max_pages
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
