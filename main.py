"""
메인 실행 파일 - 네이버 쇼핑 순위 추적기
=========================================
사용법:
  python main.py                  # 즉시 1회 추적 + HTML 리포트 생성
  python main.py --schedule       # 자동 스케줄 모드 (config 설정 간격으로 반복)
  python main.py --report-only    # 리포트만 재생성
  python main.py --history [키워드] # 특정 키워드 히스토리 출력
"""

import sys
import time
import argparse
import logging
from datetime import datetime

# ── 설정 불러오기 ──────────────────────────────────────
try:
    import config
    CLIENT_ID     = config.NAVER_CLIENT_ID
    CLIENT_SECRET = config.NAVER_CLIENT_SECRET
    STORE_NAME    = config.MY_STORE_NAME
    PRODUCT_IDS   = config.MY_PRODUCT_IDS
    KEYWORDS      = config.KEYWORDS
    MAX_PAGES     = config.MAX_PAGES
    SORT          = config.SEARCH_SORT
    DB_PATH       = config.DB_PATH
    REPORT_PATH   = config.REPORT_PATH
    SCHEDULE_H    = config.SCHEDULE_INTERVAL_HOURS
except ImportError:
    print("❌ config.py 파일을 찾을 수 없습니다. 같은 폴더에 config.py가 있는지 확인하세요.")
    sys.exit(1)

from tracker import NaverShoppingRankTracker
from report import generate_html_report

logger = logging.getLogger(__name__)


def run_once():
    """1회 순위 추적 실행"""
    print(f"\n{'='*60}")
    print(f"🛒 네이버 쇼핑 순위 트래커 실행")
    print(f"   스토어명: {STORE_NAME or '(미설정)'}")
    print(f"   상품 ID: {PRODUCT_IDS or '(미설정)'}")
    print(f"   키워드 수: {len(KEYWORDS)}개")
    print(f"   최대 탐색: {MAX_PAGES * 100}위")
    print(f"{'='*60}\n")

    # API 키 검증
    if CLIENT_ID == "여기에_클라이언트_ID_입력":
        print("⚠️  config.py에서 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정하세요!")
        print("   네이버 개발자 센터: https://developers.naver.com")
        print("\n[데모 모드] 설정 완료 후 재실행하세요.\n")
        return False

    if not STORE_NAME and not PRODUCT_IDS:
        print("⚠️  config.py에서 MY_STORE_NAME 또는 MY_PRODUCT_IDS를 설정하세요!")
        return False

    tracker = NaverShoppingRankTracker(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        my_store_name=STORE_NAME,
        my_product_ids=PRODUCT_IDS,
        db_path=DB_PATH,
    )

    results = tracker.track_all(KEYWORDS, max_pages=MAX_PAGES, sort=SORT)
    generate_html_report(DB_PATH, REPORT_PATH, KEYWORDS, days=14)

    print(f"\n🔗 리포트 확인: {REPORT_PATH}")
    return True


def run_schedule():
    """자동 스케줄 모드"""
    print(f"\n⏰ 스케줄 모드 시작 - {SCHEDULE_H}시간마다 자동 추적")
    print("   종료하려면 Ctrl+C 를 누르세요.\n")

    while True:
        run_once()
        next_run = datetime.now().strftime('%Y-%m-%d %H:%M')
        print(f"\n💤 {SCHEDULE_H}시간 후 다음 추적 예정... (시작: {next_run})")
        time.sleep(SCHEDULE_H * 3600)


def show_history(keyword: str):
    """특정 키워드의 히스토리 출력"""
    tracker = NaverShoppingRankTracker(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        my_store_name=STORE_NAME,
        my_product_ids=PRODUCT_IDS,
        db_path=DB_PATH,
    )
    rows = tracker.get_history(keyword, days=30)
    if not rows:
        print(f"'{keyword}' 키워드의 히스토리가 없습니다.")
        return

    print(f"\n📅 '{keyword}' 순위 히스토리 (최근 30일)")
    print("-" * 70)
    print(f"{'날짜/시간':<20} {'순위':>6}  {'상품명':<25} {'가격':>10}")
    print("-" * 70)
    for row in rows:
        rank_str = f"{row[1]}위" if row[1] else "미발견"
        name = (row[2] or "-")[:24]
        price = f"{row[4]:,}원" if row[4] else "-"
        print(f"{row[0]:<20} {rank_str:>6}  {name:<25} {price:>10}")


def main():
    parser = argparse.ArgumentParser(description="네이버 쇼핑 순위 트래커")
    parser.add_argument("--schedule", action="store_true", help="자동 스케줄 모드")
    parser.add_argument("--report-only", action="store_true", help="리포트만 재생성")
    parser.add_argument("--history", type=str, metavar="키워드", help="히스토리 조회")
    args = parser.parse_args()

    if args.history:
        show_history(args.history)
    elif args.report_only:
        generate_html_report(DB_PATH, REPORT_PATH, KEYWORDS, days=14)
        print(f"✅ 리포트 재생성 완료: {REPORT_PATH}")
    elif args.schedule:
        run_schedule()
    else:
        run_once()


if __name__ == "__main__":
    main()
