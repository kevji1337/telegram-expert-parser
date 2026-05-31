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

app = Flask(__name__)


def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


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

    return jsonify({"ok": True})


@app.route("/download/<file_type>")
def download(file_type: str):
    paths = {
        "full": OUTPUT_CSV,
        "shortlist": OUTPUT_SHORTLIST_CSV,
        "decomp": OUTPUT_DECOMP_CSV,
    }
    path = paths.get(file_type)
    if not path or not os.path.exists(path):
        return "Файл не найден", 404
    return send_file(path, as_attachment=True)


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
