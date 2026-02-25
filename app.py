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
    rows = {r["key"]: r["value"] for r in c.fetchall()}
    conn.close()
    return rows.get("client_id", ""), rows.get("client_secret", "")


# ──────────────────────────────────────────────────
# 메인 대시보드
# ──────────────────────────────────────────────────
@app.route("/")
def index():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM clients ORDER BY name")
    clients = c.fetchall()

    # 각 광고주별 최신 순위 요약
    summary = {}
    for cl in clients:
        c.execute("""
            SELECT keyword, product_id, rank, checked_at
            FROM rank_history
            WHERE client_id = ?
            AND id IN (
                SELECT MAX(id) FROM rank_history
                WHERE client_id = ?
                GROUP BY keyword, product_id
            )
            ORDER BY keyword, rank
        """, (cl["id"], cl["id"]))
        rows = c.fetchall()
        in_rank = sum(1 for r in rows if r["rank"] is not None)
        best = min((r["rank"] for r in rows if r["rank"]), default=None)
        summary[cl["id"]] = {
            "total_combos": len(rows),
            "in_rank": in_rank,
            "best_rank": best,
            "last_check": rows[0]["checked_at"][:16] if rows else None,
        }

    conn.close()
    return render_template("index.html", clients=clients, summary=summary)


# ──────────────────────────────────────────────────
# 설정 (API 키)
# ──────────────────────────────────────────────────
@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        cid = request.form.get("client_id", "").strip()
        csec = request.form.get("client_secret", "").strip()
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('client_id',?)", (cid,))
        c.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('client_secret',?)", (csec,))
        conn.commit()
        conn.close()
        flash("✅ API 키가 저장되었습니다.", "success")
        return redirect(url_for("settings"))

    cid, csec = get_api_keys()
    return render_template("settings.html", client_id=cid, client_secret=csec)


# ──────────────────────────────────────────────────
# 광고주 관리
# ──────────────────────────────────────────────────
@app.route("/clients/add", methods=["POST"])
def add_client():
    name = request.form.get("name", "").strip()
    memo = request.form.get("memo", "").strip()
    if not name:
        flash("광고주명을 입력하세요.", "error")
        return redirect(url_for("index"))
    conn = get_conn()
    try:
        conn.execute("INSERT INTO clients (name, memo) VALUES (?,?)", (name, memo))
        conn.commit()
        flash(f"✅ 광고주 '{name}' 추가 완료!", "success")
    except Exception as e:
        flash(f"이미 존재하는 광고주명입니다.", "error")
    conn.close()
    return redirect(url_for("index"))


@app.route("/clients/<int:cid>/delete", methods=["POST"])
def delete_client(cid):
    conn = get_conn()
    conn.execute("DELETE FROM clients WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    flash("광고주가 삭제되었습니다.", "success")
    return redirect(url_for("index"))


# ──────────────────────────────────────────────────
# 광고주 상세 (상품 + 키워드 관리 + 순위 현황)
# ──────────────────────────────────────────────────
@app.route("/clients/<int:cid>")
def client_detail(cid):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM clients WHERE id=?", (cid,))
    client = c.fetchone()
    if not client:
        return "광고주를 찾을 수 없습니다.", 404

    c.execute("SELECT * FROM products WHERE client_id=? ORDER BY id", (cid,))
    products = c.fetchall()

    c.execute("SELECT * FROM keywords WHERE client_id=? ORDER BY id", (cid,))
    keywords = c.fetchall()

    # 최신 순위 현황 (상품 × 키워드 매트릭스용)
    c.execute("""
        SELECT keyword, product_id, product_name, rank, lprice, mall_name, checked_at
        FROM rank_history
        WHERE client_id = ?
        AND id IN (
            SELECT MAX(id) FROM rank_history
            WHERE client_id = ?
            GROUP BY keyword, product_id
        )
        ORDER BY keyword, rank NULLS LAST
    """, (cid, cid))
    latest_ranks = c.fetchall()

    # 순위 히스토리 (차트용, 최근 14일)
    c.execute("""
        SELECT product_id, product_name, keyword, rank, checked_at
        FROM rank_history
        WHERE client_id = ?
          AND checked_at >= datetime('now', '-14 days', 'localtime')
        ORDER BY checked_at ASC
    """, (cid,))
    history = c.fetchall()

    conn.close()

    # 차트 데이터 구성 (상품+키워드 조합별)
    import json
    from collections import defaultdict
    chart_data = defaultdict(lambda: {"dates": [], "ranks": []})
    for row in history:
        key = f"{row['product_id']} / {row['keyword']}"
        chart_data[key]["dates"].append(row["checked_at"][:16])
        chart_data[key]["ranks"].append(row["rank"])

    return render_template("client_detail.html",
                           client=client,
                           products=products,
                           keywords=keywords,
                           latest_ranks=latest_ranks,
                           chart_data=json.dumps(dict(chart_data), ensure_ascii=False),
                           tracking=tracking_status.get(cid, None))


# ──────────────────────────────────────────────────
# 상품 추가/삭제
# ──────────────────────────────────────────────────
@app.route("/clients/<int:cid>/products/add", methods=["POST"])
def add_product(cid):
    url = request.form.get("product_url", "").strip()
    alias = request.form.get("product_name", "").strip()

    pid = parse_product_id(url)
    if not pid:
        flash(f"❌ URL에서 상품 ID를 찾을 수 없습니다: {url}", "error")
        return redirect(url_for("client_detail", cid=cid))

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO products (client_id, product_url, product_id, product_name) VALUES (?,?,?,?)",
            (cid, url, pid, alias or pid)
        )
        conn.commit()
        flash(f"✅ 상품 추가 완료 (ID: {pid})", "success")
    except Exception as e:
        flash(f"오류: {e}", "error")
    conn.close()
    return redirect(url_for("client_detail", cid=cid))


@app.route("/clients/<int:cid>/products/<int:pid>/delete", methods=["POST"])
def delete_product(cid, pid):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id=? AND client_id=?", (pid, cid))
    conn.commit()
    conn.close()
    flash("상품이 삭제되었습니다.", "success")
    return redirect(url_for("client_detail", cid=cid))


# ──────────────────────────────────────────────────
# 키워드 추가/삭제
# ──────────────────────────────────────────────────
@app.route("/clients/<int:cid>/keywords/add", methods=["POST"])
def add_keyword(cid):
    kw_raw = request.form.get("keyword", "").strip()
    added = 0
    for kw in [k.strip() for k in kw_raw.replace("\n", ",").split(",") if k.strip()]:
        conn = get_conn()
        try:
            conn.execute("INSERT OR IGNORE INTO keywords (client_id, keyword) VALUES (?,?)", (cid, kw))
            conn.commit()
            added += 1
        except:
            pass
        conn.close()
    flash(f"✅ {added}개 키워드 추가 완료!", "success")
    return redirect(url_for("client_detail", cid=cid))


@app.route("/clients/<int:cid>/keywords/<int:kid>/delete", methods=["POST"])
def delete_keyword(cid, kid):
    conn = get_conn()
    conn.execute("DELETE FROM keywords WHERE id=? AND client_id=?", (kid, cid))
    conn.commit()
    conn.close()
    flash("키워드가 삭제되었습니다.", "success")
    return redirect(url_for("client_detail", cid=cid))


# ──────────────────────────────────────────────────
# 순위 추적 실행 (비동기)
# ──────────────────────────────────────────────────
@app.route("/clients/<int:cid>/track", methods=["POST"])
def start_tracking(cid):
    if tracking_status.get(cid) == "running":
        flash("⚠️ 이미 추적 중입니다.", "warning")
        return redirect(url_for("client_detail", cid=cid))

    api_id, api_secret = get_api_keys()
    if not api_id or not api_secret:
        flash("❌ API 키를 먼저 설정하세요. (설정 메뉴)", "error")
        return redirect(url_for("client_detail", cid=cid))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT product_id, product_name FROM products WHERE client_id=?", (cid,))
    products = [dict(r) for r in c.fetchall()]
    c.execute("SELECT keyword FROM keywords WHERE client_id=?", (cid,))
    keywords = [r["keyword"] for r in c.fetchall()]
    conn.close()

    if not products:
        flash("❌ 등록된 상품이 없습니다.", "error")
        return redirect(url_for("client_detail", cid=cid))
    if not keywords:
        flash("❌ 등록된 키워드가 없습니다.", "error")
        return redirect(url_for("client_detail", cid=cid))

    def run_track():
        tracking_status[cid] = "running"
        try:
            results = track_client(api_id, api_secret, cid, products, keywords, max_pages=10)
            # DB 저장
            conn2 = get_conn()
            for r in results:
                conn2.execute("""
                    INSERT INTO rank_history
                    (client_id, product_id, product_name, keyword, rank, lprice, mall_name, checked_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (r["client_id"], r["product_id"], r["product_name"],
                      r["keyword"], r["rank"], r.get("lprice"), r.get("mall_name"), r["checked_at"]))
            conn2.commit()
            conn2.close()
            tracking_status[cid] = "done"
            logger.info(f"광고주 {cid} 추적 완료 ({len(results)}건)")
        except Exception as e:
            tracking_status[cid] = f"error: {e}"
            logger.error(f"추적 오류: {e}")

    t = threading.Thread(target=run_track, daemon=True)
    t.start()

    flash(f"🚀 순위 추적이 시작되었습니다! ({len(products)}개 상품 × {len(keywords)}개 키워드)", "success")
    return redirect(url_for("client_detail", cid=cid))


# 추적 상태 API
@app.route("/clients/<int:cid>/track/status")
def track_status(cid):
    return jsonify({"status": tracking_status.get(cid, "idle")})


# 추적 완료 후 상태 초기화
@app.route("/clients/<int:cid>/track/reset", methods=["POST"])
def reset_track_status(cid):
    tracking_status.pop(cid, None)
    return jsonify({"ok": True})


# ──────────────────────────────────────────────────
# 전체 광고주 일괄 추적
# ──────────────────────────────────────────────────
@app.route("/track/all", methods=["POST"])
def track_all():
    api_id, api_secret = get_api_keys()
    if not api_id:
        flash("❌ API 키를 먼저 설정하세요.", "error")
        return redirect(url_for("index"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM clients")
    clients = c.fetchall()
    conn.close()

    for cl in clients:
        if tracking_status.get(cl["id"]) != "running":
            # 각 광고주를 별도 스레드로 순차 실행 (API 한도 보호)
            conn2 = get_conn()
            c2 = conn2.cursor()
            c2.execute("SELECT product_id, product_name FROM products WHERE client_id=?", (cl["id"],))
            products = [dict(r) for r in c2.fetchall()]
            c2.execute("SELECT keyword FROM keywords WHERE client_id=?", (cl["id"],))
            keywords = [r["keyword"] for r in c2.fetchall()]
            conn2.close()

            if products and keywords:
                cid = cl["id"]
                def run(cid=cid, products=products, keywords=keywords):
                    tracking_status[cid] = "running"
                    try:
                        results = track_client(api_id, api_secret, cid, products, keywords)
                        conn3 = get_conn()
                        for r in results:
                            conn3.execute("""
                                INSERT INTO rank_history
                                (client_id, product_id, product_name, keyword, rank, lprice, mall_name, checked_at)
                                VALUES (?,?,?,?,?,?,?,?)
                            """, (r["client_id"], r["product_id"], r["product_name"],
                                  r["keyword"], r["rank"], r.get("lprice"), r.get("mall_name"), r["checked_at"]))
                        conn3.commit()
                        conn3.close()
                        tracking_status[cid] = "done"
                    except Exception as e:
                        tracking_status[cid] = f"error"
                threading.Thread(target=run, daemon=True).start()

    flash(f"🚀 전체 {len(clients)}개 광고주 추적 시작!", "success")
    return redirect(url_for("index"))


# 앱 시작 시 DB 초기화 (Render 배포 환경 포함)
with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*50)
    print("  네이버 쇼핑 순위 트래커 (광고대행사 버전)")
    print(f"  http://127.0.0.1:{port}  에서 접속하세요")
    print("="*50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
