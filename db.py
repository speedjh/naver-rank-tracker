"""
데이터베이스 초기화 및 헬퍼 — 클라우드 배포 버전
DB 경로: 환경변수 DB_PATH 또는 /tmp/agency.db (Render Persistent Disk 마운트 경로 대응)
"""
import sqlite3
import os

# Render Persistent Disk는 /data 에 마운트됨
# 환경변수로 경로 지정 가능 (기본: /tmp/agency.db)
_default = "/data/agency.db" if os.path.isdir("/data") else "/tmp/agency.db"
DB_PATH = os.environ.get("DB_PATH", _default)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL 모드: 동시 접속 안정성 향상 (팀원 여러 명 동시 사용 대응)
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            product_url TEXT    NOT NULL,
            product_id  TEXT    NOT NULL,
            product_name TEXT,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
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
            checked_at   TEXT    NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] 초기화 완료: {DB_PATH}")
