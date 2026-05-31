"""
Экспорт в CSV
"""
import csv
import os
from dataclasses import asdict
from models import ChannelRow


def load_manual_statuses(path: str) -> dict[str, str]:
    """Загружает ручные статусы из предыдущего CSV"""
    statuses: dict[str, str] = {}
    if not os.path.exists(path):
        return statuses
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                status = (row.get("manual_review_status") or "").strip()
                if not status or status == "не смотрел":
                    continue
                key = (row.get("username") or row.get("link") or "").strip()
                if key:
                    statuses[key] = status
    except Exception as e:
        print(f"[!] Не смог прочитать прошлый CSV для переноса пометок: {e}")
    return statuses


def save_csv(rows: list[ChannelRow], path: str) -> None:
    """Сохраняет список каналов в CSV"""
    if not rows:
        return

    prev = load_manual_statuses(path)
    if prev:
        for r in rows:
            key = r.username or r.link
            if key and key in prev:
                r.manual_review_status = prev[key]

    fields = list(asdict(rows[0]).keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
