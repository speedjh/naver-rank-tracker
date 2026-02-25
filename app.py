"""
Flask 웹 애플리케이션 v6 - 다중 광고주 탭 UI
- 광고주별 탭 전환 (클라이언트 사이드)
- 각 광고주마다 독립된 상품/키워드/순위 관리
- 모든 버튼 AJAX 동작
- 매일 오전 11시 자동 순위 추적
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import threading, logging, os, re
from datetime import datetime
from db import init_db, get_conn
from engine import parse_product_info, track_client, search_shopping

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "naver_rank_agency_2025")

tracking_status = {}
global_tracking = {"running": False, "last_run": None}

# ────────────────────────────────────────────
# 공통 헬퍼
# ────────────────────────────────────────────
def get_api_keys():
    env_id     = os.environ.get("NAVER_CLIENT_ID", "")
    env_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if env_id and env_secret:
        return env_id, env_secret
    conn = get_conn()
    rows = {r["key"]: r["value"] for r in
            conn.execute("SELECT key,value FROM settings WHERE key IN ('client_id','client_secret')").fetchall()}
    conn.close()
    return rows.get("client_id", ""), rows.get("client_secret", "")


def get_client_data(cid):
    """광고주 한 명의 rows(상품×키워드), products, keywords 반환"""
    conn = get_conn()
    c    = conn.cursor()

    # 상품 × 키워드 조합 + 최신 순위
    c.execute("""
        SELECT
            p.id          AS pid,
            p.product_id  AS product_id,
            p.product_name AS product_name,
            p.product_url  AS product_url,
            k.id           AS kid,
            k.keyword      AS keyword,
            rh.rank        AS rank,
            rh.lprice      AS lprice,
            rh.checked_at  AS checked_at
        FROM products p
        CROSS JOIN keywords k ON k.client_id = p.client_id
        LEFT JOIN rank_history rh ON (
            rh.product_id = p.product_id
            AND rh.client_id  = p.client_id
            AND rh.keyword    = k.keyword
            AND rh.id = (
                SELECT MAX(id) FROM rank_history
                WHERE product_id = p.product_id
                  AND client_id  = p.client_id
                  AND keyword    = k.keyword
            )
        )
        WHERE p.client_id=?
        ORDER BY p.id, k.id
    """, (cid,))
    combo_rows = [dict(r) for r in c.fetchall()]

    # 키워드 없는 상품 단독
    c.execute("""
        SELECT p.id AS pid, p.product_id, p.product_name, p.product_url
        FROM products p
        WHERE p.client_id=? AND NOT EXISTS (
            SELECT 1 FROM keywords k WHERE k.client_id=?
        )
    """, (cid, cid))
    for sp in c.fetchall():
        combo_rows.append({
            "pid": sp["pid"], "product_id": sp["product_id"],
            "product_name": sp["product_name"], "product_url": sp["product_url"],
            "kid": None, "keyword": "—",
            "rank": None, "lprice": None, "checked_at": None,
        })

    c.execute("SELECT id, keyword FROM keywords WHERE client_id=? ORDER BY id", (cid,))
    keywords = [dict(r) for r in c.fetchall()]

    c.execute("SELECT id, product_id, product_name, product_url FROM products WHERE client_id=? ORDER BY id", (cid,))
    products = [dict(r) for r in c.fetchall()]

    conn.close()
    return combo_rows, products, keywords


# ────────────────────────────────────────────
# 전체 추적
# ────────────────────────────────────────────
def run_all_tracking(source="manual"):
    if global_tracking["running"]:
        return
    api_id, api_secret = get_api_keys()
    if not api_id:
        logger.warning("[추적] API 키 미설정")
        return

    conn = get_conn()
    clients = conn.execute("SELECT id,name FROM clients").fetchall()
    conn.close()
    if not clients:
        return

    global_tracking["running"] = True
    logger.info(f"[추적 시작] {source} | {len(clients)}개 광고주")
    try:
        for cl in clients:
            cid = cl["id"]
            conn2 = get_conn()
            prods = [dict(r) for r in conn2.execute(
                "SELECT product_id,catalog_id,url_product_id,mall_name,product_name FROM products WHERE client_id=?", (cid,)
            ).fetchall()]
            kws = [r["keyword"] for r in conn2.execute(
                "SELECT keyword FROM keywords WHERE client_id=?", (cid,)
            ).fetchall()]
            conn2.close()
            if not prods or not kws:
                continue
            tracking_status[cid] = "running"
            try:
                results = track_client(api_id, api_secret, cid, prods, kws, max_pages=10)
                conn3 = get_conn()
                for r in results:
                    conn3.execute("""
                        INSERT INTO rank_history
                        (client_id,product_id,product_name,keyword,rank,
                         lprice,mall_name,product_type,matched_id,checked_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (r["client_id"], r["product_id"], r["product_name"],
                          r["keyword"], r["rank"], r.get("lprice"), r.get("mall_name"),
                          r.get("product_type"), r.get("matched_id"), r["checked_at"]))
                conn3.commit()
                conn3.close()
                tracking_status[cid] = "done"
                logger.info(f"  ✅ {cl['name']} 완료 ({len(results)}건)")
            except Exception as e:
                tracking_status[cid] = f"error:{e}"
                logger.error(f"  ❌ {cl['name']} 오류: {e}")
        global_tracking["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    finally:
        global_tracking["running"] = False


def scheduled_job():
    logger.info("⏰ 자동 스케줄 실행")
    threading.Thread(target=lambda: run_all_tracking("schedule"), daemon=True).start()


# ────────────────────────────────────────────
# APScheduler
# ────────────────────────────────────────────
KST = pytz.timezone("Asia/Seoul")
scheduler = BackgroundScheduler(timezone=KST)
scheduler.add_job(scheduled_job, CronTrigger(hour=11, minute=0, timezone=KST),
                  id="daily_track", replace_existing=True)
scheduler.start()
logger.info("⏰ 스케줄러 시작 — 매일 KST 11:00")


# ════════════════════════════════════════════
# 메인 대시보드
# ════════════════════════════════════════════
@app.route("/")
def index():
    conn = get_conn()
    clients = [dict(r) for r in conn.execute("SELECT id,name,memo FROM clients ORDER BY id").fetchall()]
    conn.close()

    # 광고주가 하나도 없으면 빈 상태로 시작 (자동 생성 X)
    client_data = {}
    for cl in clients:
        rows, products, keywords = get_client_data(cl["id"])
        client_data[cl["id"]] = {
            "rows": rows,
            "products": products,
            "keywords": keywords,
        }

    job = scheduler.get_job("daily_track")
    next_run = job.next_run_time.astimezone(KST).strftime("%m/%d %H:%M") if job and job.next_run_time else "-"

    return render_template("index.html",
                           clients=clients,
                           client_data=client_data,
                           global_tracking=global_tracking,
                           next_run=next_run)


# ════════════════════════════════════════════
# 광고주 CRUD (AJAX)
# ════════════════════════════════════════════
@app.route("/clients/add", methods=["POST"])
def add_client():
    name = (request.form.get("name") or request.json.get("name", "") if request.is_json else request.form.get("name","")).strip()
    if not name:
        return jsonify({"error": "광고주명을 입력하세요."}), 400
    conn = get_conn()
    try:
        conn.execute("INSERT INTO clients (name, memo) VALUES (?,?)", (name, ""))
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
    conn.close()
    return jsonify({"ok": True, "id": cid, "name": name})


@app.route("/clients/<int:cid>/delete", methods=["POST"])
def delete_client(cid):
    conn = get_conn()
    conn.execute("DELETE FROM rank_history WHERE client_id=?", (cid,))
    conn.execute("DELETE FROM keywords WHERE client_id=?", (cid,))
    conn.execute("DELETE FROM products WHERE client_id=?", (cid,))
    conn.execute("DELETE FROM clients WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ════════════════════════════════════════════
# 상품 CRUD (AJAX)
# ════════════════════════════════════════════
@app.route("/clients/<int:cid>/products/add", methods=["POST"])
def add_product(cid):
    product_url  = request.form.get("product_url", "").strip()
    product_name = request.form.get("product_name", "").strip()
    if not product_url:
        return jsonify({"error": "URL을 입력하세요."}), 400

    # 클라이언트 존재 확인
    conn = get_conn()
    if not conn.execute("SELECT id FROM clients WHERE id=?", (cid,)).fetchone():
        conn.close()
        return jsonify({"error": "존재하지 않는 광고주입니다."}), 404

    info           = parse_product_info(product_url)
    product_id     = info.get("product_id", "") or product_url
    catalog_id     = info.get("catalog_id", "")
    url_product_id = info.get("product_id", "")
    display_name   = product_name or product_id

    try:
        conn.execute("""
            INSERT OR IGNORE INTO products
            (client_id,product_url,product_id,catalog_id,url_product_id,mall_name,product_name)
            VALUES (?,?,?,?,?,?,?)
        """, (cid, product_url, product_id, catalog_id, url_product_id, "", display_name))
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
    conn.close()
    return jsonify({"ok": True, "pid": pid, "product_id": product_id, "product_name": display_name, "product_url": product_url})


@app.route("/clients/<int:cid>/products/<int:pid>/delete", methods=["POST"])
def delete_product(cid, pid):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id=? AND client_id=?", (pid, cid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ════════════════════════════════════════════
# 키워드 CRUD (AJAX)
# ════════════════════════════════════════════
@app.route("/clients/<int:cid>/keywords/add", methods=["POST"])
def add_keyword(cid):
    raw = request.form.get("keyword", "").strip()
    if not raw:
        return jsonify({"error": "키워드를 입력하세요."}), 400

    conn = get_conn()
    if not conn.execute("SELECT id FROM clients WHERE id=?", (cid,)).fetchone():
        conn.close()
        return jsonify({"error": "존재하지 않는 광고주입니다."}), 404

    kws = [k.strip() for k in re.split(r"[,\n]+", raw) if k.strip()]
    added = []
    for kw in kws:
        try:
            conn.execute("INSERT OR IGNORE INTO keywords (client_id,keyword) VALUES (?,?)", (cid, kw))
            added.append(kw)
        except Exception:
            pass
    conn.commit()

    # 추가된 keyword id 목록
    kid_map = {}
    for kw in added:
        row = conn.execute("SELECT id FROM keywords WHERE client_id=? AND keyword=?", (cid, kw)).fetchone()
        if row:
            kid_map[kw] = row["id"]
    conn.close()
    return jsonify({"ok": True, "added": added, "kid_map": kid_map})


@app.route("/clients/<int:cid>/keywords/<int:kid>/delete", methods=["POST"])
def delete_keyword(cid, kid):
    conn = get_conn()
    conn.execute("DELETE FROM keywords WHERE id=? AND client_id=?", (kid, cid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ════════════════════════════════════════════
# 추적
# ════════════════════════════════════════════
@app.route("/track/now", methods=["POST"])
def track_now():
    if global_tracking["running"]:
        return jsonify({"error": "이미 추적 중입니다."}), 409
    threading.Thread(target=lambda: run_all_tracking("manual"), daemon=True).start()
    return jsonify({"ok": True, "message": "추적을 시작했습니다."})


@app.route("/track/status")
def track_status():
    return jsonify({"running": global_tracking["running"], "last_run": global_tracking["last_run"]})


# ════════════════════════════════════════════
# 상품 검색 API
# ════════════════════════════════════════════
@app.route("/api/search-products")
def api_search_products():
    q    = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    if not q:
        return jsonify({"error": "검색어를 입력하세요."})
    api_id, api_secret = get_api_keys()
    if not api_id:
        return jsonify({"error": "Naver API 키를 먼저 설정해주세요."})
    try:
        start    = (page - 1) * 20 + 1
        data     = search_shopping(api_id, api_secret, q, display=20, start=start)
        items_raw = data.get("items", [])
        total     = data.get("total", 0)
        items = []
        for i, item in enumerate(items_raw):
            pid    = item.get("productId", "")
            ptype  = str(item.get("productType", "2"))
            is_cat = ptype == "1"
            link   = item.get("link", "")
            items.append({
                "rank":      start + i,
                "productId": pid,
                "title":     re.sub(r"<[^>]+>", "", item.get("title", "")),
                "mallName":  item.get("mallName", ""),
                "lprice":    int(item.get("lprice", 0) or 0),
                "image":     item.get("image", ""),
                "isCatalog": is_cat,
                "link":      link,
                "addUrl":    f"https://search.shopping.naver.com/catalog/{pid}" if is_cat else link,
            })
        return jsonify({"items": items, "total": total})
    except Exception as e:
        return jsonify({"error": str(e)})


# ════════════════════════════════════════════
# 히스토리 API
# ════════════════════════════════════════════
@app.route("/api/history")
def api_history():
    product_id = request.args.get("pid", "")
    keyword    = request.args.get("kw", "")
    conn = get_conn()
    rows = [{"rank": r["rank"], "date": r["checked_at"][:16]} for r in conn.execute("""
        SELECT rank, checked_at FROM rank_history
        WHERE product_id=? AND keyword=?
          AND checked_at >= datetime('now','-30 days','localtime')
        ORDER BY checked_at ASC LIMIT 60
    """, (product_id, keyword)).fetchall()]
    conn.close()
    return jsonify(rows)


# ════════════════════════════════════════════
# 설정
# ════════════════════════════════════════════
@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        cid    = request.form.get("client_id", "").strip()
        secret = request.form.get("client_secret", "").strip()
        conn   = get_conn()
        conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('client_id',?)", (cid,))
        conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('client_secret',?)", (secret,))
        conn.commit()
        conn.close()
        flash("API 키가 저장되었습니다.", "success")
        return redirect(url_for("settings"))
    api_id, api_secret = get_api_keys()
    return render_template("settings.html", client_id=api_id, client_secret=api_secret)


# ════════════════════════════════════════════
# 업무 자동화 페이지
# ════════════════════════════════════════════
@app.route("/automation")
def automation():
    return render_template("automation.html")


@app.route("/api/automation/generate", methods=["POST"])
def api_automation_generate():
    """리워드 마케팅 캠페인 구글 시트 데이터 생성 API"""
    data = request.get_json(force=True)
    start   = data.get("start", "").strip()
    end     = data.get("end", "").strip()
    keyword = data.get("keyword", "").strip()
    url     = data.get("url", "").strip()
    name    = data.get("name", "").strip()
    daily   = data.get("daily", "").strip()
    pid     = data.get("pid", "").strip()
    store   = data.get("store", "").strip()
    mission = data.get("mission", "").strip()

    def blur_word(w):
        if len(w) <= 1: return w
        if len(w) == 2: return '*' + w[1]
        return w[0] + '*' + w[2:]

    def blur_name(n):
        words = n.split()
        return ' '.join([words[0]] + [blur_word(w) for w in words[1:]]) if words else n

    blurred = blur_name(name)
    mission_text = (mission
        .replace("{keyword}", keyword or "키워드")
        .replace("{blurred_name}", blurred or name)
        .replace("{product_name}", name))

    pid3 = pid[:3] if pid else ""
    pid5 = pid[:5] if pid else ""

    rows = []
    for i in range(5):
        rows.append({
            "row": 3 + i,
            "B": "WEB",
            "C": start if i == 0 else "",
            "D": end   if i == 0 else "",
            "E": "", "F": "", "G": "", "H": "",
            "I": pid3,
            "J": mission_text if i == 0 else "",
            "K": pid5,
            "L": url,
            "M": store,
            "N": daily if i == 0 else "",
        })

    tsv = "\n".join(
        "\t".join([r["B"],r["C"],r["D"],"","","","",r["I"],r["J"],r["K"],r["L"],r["M"],r["N"]])
        for r in rows
    )
    return jsonify({"ok": True, "rows": rows, "tsv": tsv, "blurred_name": blurred})


# 하위 호환 라우트 (구버전 경로 리다이렉트)
@app.route("/products/add", methods=["POST"])
def add_product_compat():
    return redirect(url_for("index"))

@app.route("/keywords/add", methods=["POST"])
def add_keyword_compat():
    return redirect(url_for("index"))


with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
