"""
데이터베이스 초기화 및 헬퍼 — 가격비교 카탈로그 대응 버전
"""
import sqlite3
import os

_default = "/data/agency.db" if os.path.isdir("/data") else "/tmp/agency.db"
DB_PATH = os.environ.get("DB_PATH", _default)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            memo        TEXT,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # products 테이블: catalog_id + mall_name 추가
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE
... (output truncated, click Expand to see full output)
