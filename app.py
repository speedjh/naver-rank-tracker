"""
Flask 웹 애플리케이션 - 광고대행사용 네이버 쇼핑 순위 트래커
"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import threading
import logging
import os
from db import init_db, get_conn, DB_PATH
from engine import parse_product_id, track_client, find_rank

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
# 환경변수로 시크릿 키 관리 (Render 환경변수에서 설정)
app.secret_key = os.environ.get("SECRET_KEY", "naver_rank_agency_2025_change_me")

# 추적 중 상태 (광고주 ID → 진행률)
tracking_status = {}


def get_api_keys():
    # 1순위: 환경변수 (Render 대시보드에서 설정)
    env_id = os.environ.get("NAVER_CLIENT_ID", "")
    env_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if env_id and env_secret:
        return env_id, env_secret
    # 2순위: DB 저장값 (설정 화면에서 입력)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings WHERE key IN ('client_id','client_secret')")
    rows =
... (output truncated, click Expand to see full output)
