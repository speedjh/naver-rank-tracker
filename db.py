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

    # products 테이블: catalog_id + mall_name + url_product_id 추가
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            product_url     TEXT    NOT NULL,
            product_id      TEXT    NOT NULL,
            catalog_id      TEXT,              -- 가격비교 카탈로그 ID
            url_product_id  TEXT,              -- 스마트스토어 products/{숫자} → API link 매칭용 ★
            mall_name       TEXT,              -- 스토어명 (4순위 fallback)
            product_name    TEXT,
            created_at      TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # 기존 테이블에 컬럼 추가 (마이그레이션)
    for col, col_type in [("catalog_id", "TEXT"), ("mall_name", "TEXT"), ("url_product_id", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE products ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            keyword     TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now','localtime')),
            UNIQUE(client_id, keyword)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS rank_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            product_id   TEXT    NOT NULL,
            product_name TEXT,
            keyword      TEXT    NOT NULL,
            rank         INTEGER,
            lprice       INTEGER,
            mall_name    TEXT,
            product_type INTEGER,           -- 1=가격비교, 2=일반비매칭, 3=일반매칭
            matched_id   TEXT,              -- 실제 매칭된 API productId
            checked_at   TEXT    NOT NULL
        )
    """)

    # rank_history 마이그레이션
    for col, col_type in [("product_type", "INTEGER"), ("matched_id", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE rank_history ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] 초기화 완료: {DB_PATH}")
