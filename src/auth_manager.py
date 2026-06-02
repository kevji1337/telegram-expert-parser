"""Web-friendly Telegram session authorization manager."""
import asyncio
import glob
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError

from config import ACCOUNT_CONFIGS, SESSIONS_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
PHONE_RE = re.compile(r"^\+\d{7,15}$")


ACTIVE_STATUSES = {"starting", "connecting", "checking", "sending_code", "waiting_code", "waiting_password"}


@dataclass
class AuthFlow:
    account: str
    phone: str
    status: str = "starting"
    message: str = "Готовлю авторизацию"
    error: str = ""
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    code_queue: Queue = field(default_factory=Queue)
    password_queue: Queue = field(default_factory=Queue)
    thread: threading.Thread | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "account": self.account,
            "phone": self.phone,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "active": self.status in ACTIVE_STATUSES,
        }


class TelegramAuthManager:
    def __init__(self):
        self._flows: dict[str, AuthFlow] = {}
        self._lock = threading.Lock()

    def list_accounts(self) -> list[dict[str, Any]]:
        accounts = []
        for account, cfg in ACCOUNT_CONFIGS.items():
            flow = self.get_flow(account)
            session_path = cfg["session"]
            accounts.append({
                "account": account,
                "api_id": cfg["api_id"],
                "default_phone": account if account.startswith("+") else "",
                "session_path": session_path,
                "session_file": self._session_file(session_path),
                "session_exists": self._session_exists(session_path),
                "auth": flow,
            })
        return accounts

    def get_flow(self, account: str) -> dict[str, Any] | None:
        self._ensure_account(account)
        with self._lock:
            flow = self._flows.get(account)
            return flow.snapshot() if flow else None

    def start_auth(self, account: str, phone: str = "") -> dict[str, Any]:
        self._ensure_account(account)
        phone = (phone or "").strip()
        if not phone and account.startswith("+"):
            phone = account
        if not phone:
            raise ValueError("Укажи номер телефона для этого аккаунта")

        with self._lock:
            current = self._flows.get(account)
            if current and current.status in ACTIVE_STATUSES:
                raise RuntimeError("Авторизация этого аккаунта уже идёт")

            flow = AuthFlow(account=account, phone=phone)
            self._flows[account] = flow
            thread = threading.Thread(target=self._run_auth_thread, args=(flow,), daemon=True)
            flow.thread = thread
            thread.start()
            return flow.snapshot()

    def submit_code(self, account: str, code: str) -> dict[str, Any]:
        code = (code or "").replace(" ", "").strip()
        if not code:
            raise ValueError("Код не может быть пустым")
        flow = self._require_flow(account)
        if flow.status != "waiting_code":
            raise RuntimeError("Сейчас код Telegram не ожидается")
        flow.code_queue.put(code)
        return self.get_flow(account) or flow.snapshot()

    def submit_password(self, account: str, password: str) -> dict[str, Any]:
        if not password:
            raise ValueError("Пароль 2FA не может быть пустым")
        flow = self._require_flow(account)
        if flow.status != "waiting_password":
            raise RuntimeError("Сейчас пароль 2FA не ожидается")
        flow.password_queue.put(password)
        return self.get_flow(account) or flow.snapshot()

    def cancel(self, account: str) -> dict[str, Any]:
        flow = self._require_flow(account)
        if flow.status in ACTIVE_STATUSES:
            flow.code_queue.put(None)
            flow.password_queue.put(None)
            self._set_flow(flow, "canceled", "Авторизация отменена")
        return flow.snapshot()

    def delete_session(self, account: str) -> dict[str, Any]:
        self._ensure_account(account)
        with self._lock:
            flow = self._flows.get(account)
            if flow and flow.status in ACTIVE_STATUSES:
                flow.code_queue.put(None)
                flow.password_queue.put(None)
                flow.status = "canceled"
                flow.message = "Авторизация прервана: удаление сессии"
            self._flows.pop(account, None)

        cfg = ACCOUNT_CONFIGS[account]
        session_path = cfg["session"]
        removed = []
        for suffix in (".session", ".session-journal", ".session-wal", ".session-shm", ""):
            candidate = session_path + suffix if suffix else session_path
            if os.path.isfile(candidate):
                try:
                    os.remove(candidate)
                    removed.append(os.path.basename(candidate))
                except OSError:
                    pass
        return {
            "account": account,
            "removed": removed,
            "session_exists": self._session_exists(session_path),
        }

    def check_all_accounts(self) -> list[dict[str, Any]]:
        results = []
        for account in list(ACCOUNT_CONFIGS.keys()):
            try:
                results.append(self.check_account(account))
            except Exception as e:
                results.append({
                    "account": account,
                    "authorized": False,
                    "status": "error",
                    "message": "Не удалось проверить",
                    "error": self._safe_error(e),
                })
        return results

    def add_account(self, phone: str, api_id: Any, api_hash: str) -> dict[str, Any]:
        phone = (phone or "").strip()
        api_hash = (api_hash or "").strip()
        if not PHONE_RE.match(phone):
            raise ValueError("Телефон должен быть в формате +<7-15 цифр>")
        try:
            api_id_int = int(str(api_id).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("api_id должен быть числом") from exc
        if not api_hash or len(api_hash) < 8:
            raise ValueError("api_hash слишком короткий")
        if phone in ACCOUNT_CONFIGS:
            raise ValueError("Этот аккаунт уже есть в .env")

        self._write_account_to_env(phone, api_id_int, api_hash)
        ACCOUNT_CONFIGS[phone] = {
            "api_id": api_id_int,
            "api_hash": api_hash,
            "session": os.path.join(SESSIONS_DIR, phone),
        }
        return {
            "account": phone,
            "api_id": api_id_int,
            "session_path": ACCOUNT_CONFIGS[phone]["session"],
        }

    def remove_account(self, account: str, delete_session: bool = True) -> dict[str, Any]:
        self._ensure_account(account)
        with self._lock:
            flow = self._flows.get(account)
            if flow and flow.status in ACTIVE_STATUSES:
                flow.code_queue.put(None)
                flow.password_queue.put(None)
            self._flows.pop(account, None)

        removed_session = []
        if delete_session:
            removed_session = self.delete_session(account).get("removed", [])

        self._remove_account_from_env(account)
        ACCOUNT_CONFIGS.pop(account, None)
        return {"account": account, "removed_session": removed_session}

    def _write_account_to_env(self, phone: str, api_id: int, api_hash: str) -> None:
        ENV_FILE.touch(exist_ok=True)
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

        existing_accounts = []
        accounts_line_idx = None
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("TG_ACCOUNTS="):
                accounts_line_idx = i
                existing_accounts = [
                    a.strip() for a in stripped[len("TG_ACCOUNTS="):].split(",") if a.strip()
                ]
                break

        if phone not in existing_accounts:
            existing_accounts.append(phone)
        new_accounts_line = "TG_ACCOUNTS=" + ", ".join(existing_accounts)
        if accounts_line_idx is None:
            lines.insert(0, new_accounts_line)
        else:
            lines[accounts_line_idx] = new_accounts_line

        if any(line.startswith(f"TG_API_ID_{phone}=") for line in lines):
            lines = [
                f"TG_API_ID_{phone}={api_id}" if line.startswith(f"TG_API_ID_{phone}=") else line
                for line in lines
            ]
        else:
            lines.extend(["", f"# {phone}", f"TG_API_ID_{phone}={api_id}"])

        if any(line.startswith(f"TG_API_HASH_{phone}=") for line in lines):
            lines = [
                f"TG_API_HASH_{phone}={api_hash}" if line.startswith(f"TG_API_HASH_{phone}=") else line
                for line in lines
            ]
        else:
            lines.append(f"TG_API_HASH_{phone}={api_hash}")

        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _remove_account_from_env(self, phone: str) -> None:
        if not ENV_FILE.exists():
            return
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        new_lines = []
        skip_next_comment = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("TG_ACCOUNTS="):
                accounts = [
                    a.strip() for a in stripped[len("TG_ACCOUNTS="):].split(",") if a.strip()
                ]
                accounts = [a for a in accounts if a != phone]
                new_lines.append("TG_ACCOUNTS=" + ", ".join(accounts))
                continue
            if stripped == f"# {phone}":
                skip_next_comment = True
                continue
            if stripped.startswith(f"TG_API_ID_{phone}=") or stripped.startswith(f"TG_API_HASH_{phone}="):
                continue
            if skip_next_comment and not stripped:
                skip_next_comment = False
                continue
            skip_next_comment = False
            new_lines.append(line)
        ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def check_account(self, account: str) -> dict[str, Any]:
        self._ensure_account(account)
        cfg = ACCOUNT_CONFIGS[account]
        session_path = cfg["session"]
        result = {
            "account": account,
            "session_path": session_path,
            "session_file": self._session_file(session_path),
            "session_exists": self._session_exists(session_path),
            "authorized": False,
            "status": "missing_session",
            "message": "Файл сессии не найден",
            "user": None,
            "error": "",
        }
        if not result["session_exists"]:
            return result

        try:
            checked = asyncio.run(self._check_account_async(account))
            result.update(checked)
        except Exception as e:
            result.update({
                "status": "error",
                "message": "Не удалось проверить сессию",
                "error": self._safe_error(e),
            })
        return result

    async def _check_account_async(self, account: str) -> dict[str, Any]:
        cfg = ACCOUNT_CONFIGS[account]
        client = TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])
        try:
            await asyncio.wait_for(client.connect(), timeout=25)
            authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=25)
            user = None
            if authorized:
                me = await asyncio.wait_for(client.get_me(), timeout=25)
                user = {
                    "id": getattr(me, "id", None),
                    "phone": getattr(me, "phone", None),
                    "username": getattr(me, "username", None),
                    "first_name": getattr(me, "first_name", None),
                    "last_name": getattr(me, "last_name", None),
                }
            return {
                "authorized": authorized,
                "status": "authorized" if authorized else "unauthorized",
                "message": "Сессия авторизована" if authorized else "Сессия есть, но аккаунт не авторизован",
                "user": user,
                "error": "",
            }
        finally:
            await client.disconnect()

    def _run_auth_thread(self, flow: AuthFlow) -> None:
        try:
            asyncio.run(self._run_auth(flow))
        except Exception as e:
            self._set_flow(flow, "error", "Авторизация не удалась", self._safe_error(e))

    async def _run_auth(self, flow: AuthFlow) -> None:
        cfg = ACCOUNT_CONFIGS[flow.account]
        client = TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])
        try:
            self._set_flow(flow, "connecting", "Подключаюсь к Telegram")
            await client.connect()

            self._set_flow(flow, "checking", "Проверяю текущую сессию")
            if await client.is_user_authorized():
                self._set_flow(flow, "authorized", "Сессия уже авторизована")
                return

            self._set_flow(flow, "sending_code", "Отправляю код Telegram")
            sent = await client.send_code_request(flow.phone)
            phone_code_hash = getattr(sent, "phone_code_hash", None)

            self._set_flow(flow, "waiting_code", "Код отправлен. Введи его в веб-панели")
            code = await self._wait_for_input(flow.code_queue)
            if code is None:
                self._set_flow(flow, "canceled", "Авторизация отменена")
                return

            try:
                kwargs: dict[str, Any] = {"phone": flow.phone, "code": code}
                if phone_code_hash:
                    kwargs["phone_code_hash"] = phone_code_hash
                await client.sign_in(**kwargs)
            except SessionPasswordNeededError:
                self._set_flow(flow, "waiting_password", "Включена 2FA. Введи пароль")
                password = await self._wait_for_input(flow.password_queue)
                if password is None:
                    self._set_flow(flow, "canceled", "Авторизация отменена")
                    return
                await client.sign_in(password=password)

            if await client.is_user_authorized():
                self._set_flow(flow, "authorized", "Готово: сессия сохранена")
            else:
                self._set_flow(flow, "error", "Telegram не подтвердил авторизацию", "unauthorized")
        except FloodWaitError as e:
            self._set_flow(flow, "error", f"Telegram просит подождать {e.seconds} сек", f"FloodWait {e.seconds}s")
        finally:
            await client.disconnect()

    async def _wait_for_input(self, queue: Queue) -> str | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, queue.get)

    def _require_flow(self, account: str) -> AuthFlow:
        self._ensure_account(account)
        with self._lock:
            flow = self._flows.get(account)
        if not flow:
            raise RuntimeError("Авторизация для этого аккаунта не запущена")
        return flow

    def _ensure_account(self, account: str) -> None:
        if account not in ACCOUNT_CONFIGS:
            raise KeyError("Аккаунт не найден в .env")

    def _set_flow(self, flow: AuthFlow, status: str, message: str = "", error: str = "") -> None:
        with self._lock:
            flow.status = status
            flow.message = message
            flow.error = error
            flow.updated_at = time.time()

    def _session_exists(self, session_path: str) -> bool:
        return os.path.exists(self._session_file(session_path)) or os.path.exists(session_path)

    def _session_file(self, session_path: str) -> str:
        return session_path if session_path.endswith(".session") else f"{session_path}.session"

    def _safe_error(self, error: Exception) -> str:
        if isinstance(error, KeyError):
            return str(error).strip("'")
        return f"{type(error).__name__}: {error}"


telegram_auth_manager = TelegramAuthManager()
