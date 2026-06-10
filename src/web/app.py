"""
Веб-интерфейс для просмотра результатов парсера и управления им
Запуск: python run_web.py
URL: http://localhost:5000
"""
import csv
import json
import os
import sys
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_CSV, OUTPUT_SHORTLIST_CSV, OUTPUT_DECOMP_CSV
from parser_runner import parser_runner
from auth_manager import telegram_auth_manager

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"

app = Flask(__name__, static_folder=str(PUBLIC_DIR), static_url_path="/public")


_csv_cache: dict[str, tuple[float, list[dict]]] = {}


def load_csv(path: str) -> list[dict]:
    """CSV cached by mtime — re-read only when file changes."""
    if not os.path.exists(path):
        _csv_cache.pop(path, None)
        return []
    mtime = os.path.getmtime(path)
    cached = _csv_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    _csv_cache[path] = (mtime, rows)
    return rows


def invalidate_csv_cache(path: str | None = None) -> None:
    if path is None:
        _csv_cache.clear()
    else:
        _csv_cache.pop(path, None)


def filter_rows(rows: list[dict], filters: dict) -> list[dict]:
    result = []
    for row in rows:
        if filters.get("priority") and row.get("analysis_priority") != filters["priority"]:
            continue
        if filters.get("channel_type") and row.get("channel_type") != filters["channel_type"]:
            continue
        if filters.get("min_subs"):
            try:
                if int(row.get("participants_count", 0) or 0) < int(filters["min_subs"]):
                    continue
            except (ValueError, TypeError):
                continue
        if filters.get("expert_only") == "1":
            if row.get("is_expert_channel") not in ("True", "true", "1"):
                continue
        if filters.get("no_fp") == "1":
            if row.get("false_positive_reason"):
                continue
        if filters.get("niche"):
            if filters["niche"].lower() not in (row.get("matched_niches", "") or "").lower():
                continue
        if filters.get("min_score"):
            try:
                if int(row.get("expert_score", 0) or 0) < int(filters["min_score"]):
                    continue
            except (ValueError, TypeError):
                continue
        if filters.get("search"):
            q = filters["search"].lower()
            if q not in (row.get("title", "") or "").lower() and q not in (row.get("about", "") or "").lower():
                continue
        result.append(row)
    return result


def calc_stats(rows: list[dict], filtered_count: int) -> dict:
    return {
        "total": len(rows),
        "filtered": filtered_count,
        "analyze": sum(1 for r in rows if r.get("analysis_priority") == "ANALYZE"),
        "reserve": sum(1 for r in rows if r.get("analysis_priority") == "RESERVE"),
        "ignore": sum(1 for r in rows if r.get("analysis_priority") == "IGNORE"),
        "expert": sum(1 for r in rows if r.get("is_expert_channel") in ("True", "true", "1")),
        "selected": sum(1 for r in rows if r.get("selected_for_manual_analysis") in ("True", "true", "1")),
    }


# === Главные страницы ===

@app.route("/")
def index():
    rows = load_csv(OUTPUT_CSV)

    filters = {k: request.args.get(k, "") for k in [
        "priority", "channel_type", "min_subs", "expert_only", "no_fp",
        "niche", "min_score", "search"
    ]}

    filtered = filter_rows(rows, filters)

    sort_by = request.args.get("sort", "analysis_queue_score")
    reverse = request.args.get("order", "desc") == "desc"
    try:
        filtered.sort(key=lambda r: float(r.get(sort_by, 0) or 0), reverse=reverse)
    except (ValueError, TypeError):
        filtered.sort(key=lambda r: r.get(sort_by, ""), reverse=reverse)

    stats = calc_stats(rows, len(filtered))

    all_niches = set()
    for r in rows:
        for n in (r.get("matched_niches", "") or "").split(","):
            if n.strip():
                all_niches.add(n.strip())

    return render_template(
        "index.html",
        rows=filtered[:200],
        stats=stats,
        filters=filters,
        niches=sorted(all_niches),
        sort_by=sort_by,
    )


@app.route("/shortlist")
def shortlist():
    rows = load_csv(OUTPUT_SHORTLIST_CSV)
    return render_template("shortlist.html", rows=rows, title="Шортлист", subtitle="Топ-20 для ручного анализа")


@app.route("/decomposition")
def decomposition():
    rows = load_csv(OUTPUT_DECOMP_CSV)
    return render_template("shortlist.html", rows=rows, title="Декомпозиция", subtitle="Топ-5 для декомпозиции")


@app.route("/channel/<int:idx>")
def channel_detail(idx: int):
    rows = load_csv(OUTPUT_CSV)
    if idx >= len(rows):
        return "Канал не найден", 404
    return render_template("channel.html", row=rows[idx], idx=idx)


@app.route("/parser")
def parser_page():
    """Страница управления парсером"""
    return render_template("parser.html")


@app.route("/accounts")
def accounts_page():
    """Страница Telegram-аккаунтов и сессий"""
    return render_template("accounts.html")


@app.route("/dashboard")
def dashboard():
    """Дашборд с графиками распределений"""
    return render_template("dashboard.html")


@app.route("/api/dashboard_data")
def api_dashboard_data():
    """Агрегаты для графиков на дашборде"""
    rows = load_csv(OUTPUT_CSV)

    def _int(v, default=0):
        try:
            return int(float(v or 0))
        except (ValueError, TypeError):
            return default

    def _float(v, default=0.0):
        try:
            return float(v or 0)
        except (ValueError, TypeError):
            return default

    niche_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    priority_counts = {"ANALYZE": 0, "RESERVE": 0, "IGNORE": 0}
    expert_score_buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    growth_buckets = {"<0%": 0, "0%": 0, "0-1%": 0, "1-5%": 0, ">5%": 0}
    verified_count = 0
    scam_count = 0

    top_growers = []

    for r in rows:
        for n in (r.get("matched_niches", "") or "").split(","):
            n = n.strip()
            if n:
                niche_counts[n] = niche_counts.get(n, 0) + 1

        t = (r.get("channel_type") or "unknown").strip()
        type_counts[t] = type_counts.get(t, 0) + 1

        p = (r.get("analysis_priority") or "IGNORE").strip()
        if p in priority_counts:
            priority_counts[p] += 1

        es = _int(r.get("expert_score"))
        if es < 20:
            expert_score_buckets["0-20"] += 1
        elif es < 40:
            expert_score_buckets["20-40"] += 1
        elif es < 60:
            expert_score_buckets["40-60"] += 1
        elif es < 80:
            expert_score_buckets["60-80"] += 1
        else:
            expert_score_buckets["80-100"] += 1

        gr = _float(r.get("growth_rate"))
        if gr < 0:
            growth_buckets["<0%"] += 1
        elif gr == 0:
            growth_buckets["0%"] += 1
        elif gr <= 1:
            growth_buckets["0-1%"] += 1
        elif gr <= 5:
            growth_buckets["1-5%"] += 1
        else:
            growth_buckets[">5%"] += 1

        if r.get("is_verified") in ("True", "true", "1"):
            verified_count += 1
        if r.get("is_scam") in ("True", "true", "1"):
            scam_count += 1

        if gr > 0:
            top_growers.append({
                "title": r.get("title") or r.get("username") or "?",
                "username": r.get("username") or "",
                "link": r.get("link") or "",
                "growth_rate": gr,
                "participants_count": _int(r.get("participants_count")),
            })

    top_growers.sort(key=lambda x: x["growth_rate"], reverse=True)

    return jsonify({
        "totals": {
            "total": len(rows),
            "verified": verified_count,
            "scam": scam_count,
        },
        "niches": niche_counts,
        "types": type_counts,
        "priorities": priority_counts,
        "expert_score_buckets": expert_score_buckets,
        "growth_buckets": growth_buckets,
        "top_growers": top_growers[:10],
    })


# === API: статистика и обновление ===

@app.route("/api/stats")
def api_stats():
    rows = load_csv(OUTPUT_CSV)
    return jsonify(calc_stats(rows, len(rows)))


@app.route("/api/update_status", methods=["POST"])
def update_status():
    data = request.json
    idx = data.get("idx")
    status = data.get("status")

    rows = load_csv(OUTPUT_CSV)
    if idx is None or idx >= len(rows):
        return jsonify({"error": "Канал не найден"}), 404

    rows[idx]["manual_review_status"] = status

    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    invalidate_csv_cache(OUTPUT_CSV)
    return jsonify({"ok": True})


@app.route("/download/<file_type>")
def download(file_type: str):
    paths = {
        "full": OUTPUT_CSV,
        "shortlist": OUTPUT_SHORTLIST_CSV,
        "decomp": OUTPUT_DECOMP_CSV,
    }
    rel = paths.get(file_type)
    if not rel:
        return "Файл не найден", 404
    path = rel if os.path.isabs(rel) else os.path.join(PROJECT_ROOT, rel)
    if not os.path.exists(path):
        return "Файл не найден", 404
    return send_file(path, as_attachment=True)


# === API: Telegram-аккаунты и авторизация ===


def _json_error(error: Exception, status: int = 400):
    return jsonify({"error": str(error).strip("'")}), status


@app.route("/api/accounts")
def api_accounts():
    return jsonify({"accounts": telegram_auth_manager.list_accounts()})


@app.route("/api/accounts/<account>/check", methods=["POST"])
def api_account_check(account: str):
    try:
        return jsonify(telegram_auth_manager.check_account(account))
    except KeyError as e:
        return _json_error(e, 404)
    except Exception as e:
        return _json_error(e)


@app.route("/api/accounts/<account>/auth/status")
def api_account_auth_status(account: str):
    try:
        flow = telegram_auth_manager.get_flow(account)
        return jsonify(flow or {"account": account, "status": "idle", "message": "Авторизация не запущена", "active": False})
    except KeyError as e:
        return _json_error(e, 404)


@app.route("/api/accounts/<account>/auth/start", methods=["POST"])
def api_account_auth_start(account: str):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(telegram_auth_manager.start_auth(account, data.get("phone", "")))
    except KeyError as e:
        return _json_error(e, 404)
    except (RuntimeError, ValueError) as e:
        return _json_error(e)


@app.route("/api/accounts/<account>/auth/code", methods=["POST"])
def api_account_auth_code(account: str):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(telegram_auth_manager.submit_code(account, data.get("code", "")))
    except KeyError as e:
        return _json_error(e, 404)
    except (RuntimeError, ValueError) as e:
        return _json_error(e)


@app.route("/api/accounts/<account>/auth/password", methods=["POST"])
def api_account_auth_password(account: str):
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(telegram_auth_manager.submit_password(account, data.get("password", "")))
    except KeyError as e:
        return _json_error(e, 404)
    except (RuntimeError, ValueError) as e:
        return _json_error(e)


@app.route("/api/accounts/<account>/auth/cancel", methods=["POST"])
def api_account_auth_cancel(account: str):
    try:
        return jsonify(telegram_auth_manager.cancel(account))
    except KeyError as e:
        return _json_error(e, 404)
    except RuntimeError as e:
        return _json_error(e)


@app.route("/api/accounts/<account>/session", methods=["DELETE"])
def api_account_session_delete(account: str):
    try:
        return jsonify(telegram_auth_manager.delete_session(account))
    except KeyError as e:
        return _json_error(e, 404)
    except Exception as e:
        return _json_error(e)


@app.route("/api/accounts/check_all", methods=["POST"])
def api_accounts_check_all():
    try:
        return jsonify({"results": telegram_auth_manager.check_all_accounts()})
    except Exception as e:
        return _json_error(e)


@app.route("/api/accounts/add", methods=["POST"])
def api_accounts_add():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(telegram_auth_manager.add_account(
            data.get("phone", ""),
            data.get("api_id", ""),
            data.get("api_hash", ""),
        ))
    except ValueError as e:
        return _json_error(e)
    except Exception as e:
        return _json_error(e, 500)


@app.route("/api/accounts/<account>", methods=["DELETE"])
def api_account_remove(account: str):
    delete_session = request.args.get("delete_session", "1") == "1"
    try:
        return jsonify(telegram_auth_manager.remove_account(account, delete_session=delete_session))
    except KeyError as e:
        return _json_error(e, 404)
    except Exception as e:
        return _json_error(e)


# === API: управление парсером ===

@app.route("/api/parser/status")
def parser_status():
    """Текущий статус парсера"""
    return jsonify(parser_runner.get_status())


@app.route("/api/parser/start", methods=["POST"])
def parser_start():
    """Запускает парсер в фоне"""
    try:
        parser_runner.start()
        return jsonify({"ok": True, "status": "running"})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/parser/stop", methods=["POST"])
def parser_stop():
    """Останавливает парсер"""
    parser_runner.stop()
    return jsonify({"ok": True})


@app.route("/api/parser/logs")
def parser_logs():
    """Возвращает логи начиная с since"""
    since = int(request.args.get("since", 0))
    logs = parser_runner.get_logs(since)
    return jsonify({
        "logs": logs,
        "next": since + len(logs),
        "status": parser_runner.status,
    })


@app.route("/api/parser/stream")
def parser_stream():
    """Server-Sent Events: стримит логи в реальном времени"""
    def generate():
        last_idx = 0
        while True:
            logs = parser_runner.get_logs(last_idx)
            if logs:
                for line in logs:
                    payload = json.dumps({"line": line, "status": parser_runner.status})
                    yield f"data: {payload}\n\n"
                last_idx += len(logs)
            else:
                # heartbeat
                yield f": ping\n\n"

            # Если парсер закончил и логов больше нет — закрываем
            if parser_runner.status in ("finished", "error", "idle") and not logs:
                payload = json.dumps({"line": None, "status": parser_runner.status, "done": True})
                yield f"data: {payload}\n\n"
                break

            time.sleep(1)

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("Веб-интерфейс запущен на http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
