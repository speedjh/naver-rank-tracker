"""
네이버 쇼핑 상품 순위 추적기 - 설정 파일
===========================================
네이버 개발자 센터(https://developers.naver.com)에서 앱 등록 후 키를 발급받으세요.
"""

# ===== 네이버 API 인증 정보 =====
NAVER_CLIENT_ID = "여기에_클라이언트_ID_입력"
NAVER_CLIENT_SECRET = "여기에_클라이언트_SECRET_입력"

# ===== 내 상품/스토어 식별 정보 =====
# mallName: 스마트스토어명 또는 쇼핑몰명 (부분 일치 검색)
# product_ids: 네이버 쇼핑 상품 ID 목록 (정확한 매칭, 우선순위 높음)
MY_STORE_NAME = "내스토어이름"  # 예: "신세계몰", "쿠팡"
MY_PRODUCT_IDS = [
    # "12345678901",  # 상품 ID 예시
]

# ===== 추적할 키워드 설정 =====
KEYWORDS = [
    "무선이어폰",
    "블루투스 이어폰",
    "노이즈캔슬링 이어폰",
    # 원하는 키워드 추가...
]

# ===== 검색 설정 =====
MAX_PAGES = 10          # 최대 탐색 페이지 수 (1페이지 = 100개, 최대 10페이지 = 1000위까지)
DISPLAY_PER_PAGE = 100  # 페이지당 결과 수 (최대 100)
SEARCH_SORT = "sim"     # sim: 정확도순(기본/권장), date: 날짜순, asc: 가격오름, dsc: 가격내림

# ===== 스케줄러 설정 =====
SCHEDULE_INTERVAL_HOURS = 6  # 몇 시간마다 자동 추적 (기본 6시간)

# ===== 데이터베이스 경로 =====
DB_PATH = "naver_rank_tracker.db"

# ===== 리포트 출력 경로 =====
REPORT_PATH = "rank_report.html"
