"""
Загрузка ниш и прогресса (JSON-кэши заменены на SQLiteCache)
"""
import json
import os
from typing import Any
import yaml


def load_progress(path: str) -> dict[str, Any]:
    """Загружает прогресс из файла"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_progress(state: dict[str, Any], path: str) -> None:
    """Сохраняет прогресс в файл"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Не смог сохранить прогресс {path}: {e}")


def load_niches(path: str) -> list[tuple[str, str, list[str]]]:
    """Загружает ниши из keywords.yaml"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    out: list[tuple[str, str, list[str]]] = []
    for key, info in (data.get("niches") or {}).items():
        title = info.get("title", key)
        keywords = info.get("keywords") or []
        out.append((key, title, keywords))
    return out
