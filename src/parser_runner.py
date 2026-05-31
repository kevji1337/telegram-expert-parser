"""
Запуск парсера в фоновом потоке + перехват логов для веб-интерфейса
"""
import asyncio
import io
import threading
import time
from datetime import datetime
from collections import deque
from typing import Optional


class ParserRunner:
    """Управляет фоновым запуском парсера + хранит логи для SSE"""

    def __init__(self, max_log_lines: int = 2000):
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.task: Optional[asyncio.Task] = None
        self.logs: deque[str] = deque(maxlen=max_log_lines)
        self.status = "idle"  # idle | running | finished | error
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def log(self, message: str):
        """Добавляет строку в лог с таймстампом"""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        with self._lock:
            self.logs.append(line)

    def get_logs(self, since: int = 0) -> list[str]:
        """Возвращает логи начиная с индекса since"""
        with self._lock:
            all_logs = list(self.logs)
        if since >= len(all_logs):
            return []
        return all_logs[since:]

    def get_status(self) -> dict:
        """Возвращает текущий статус"""
        with self._lock:
            log_count = len(self.logs)
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "log_count": log_count,
            "error": self.error_message,
            "is_running": self.status == "running",
        }

    def is_running(self) -> bool:
        return self.status == "running"

    def start(self):
        """Запускает парсер в фоновом потоке"""
        if self.is_running():
            raise RuntimeError("Парсер уже запущен")

        self.logs.clear()
        self.status = "running"
        self.started_at = datetime.now()
        self.finished_at = None
        self.error_message = None
        self._stop_event.clear()

        self.thread = threading.Thread(target=self._run_thread, daemon=True)
        self.thread.start()

    def stop(self):
        """Останавливает парсер (мягкая остановка)"""
        if not self.is_running():
            return
        self._stop_event.set()
        self.log("[!] Запрошена остановка парсера...")

        if self.loop and self.task:
            self.loop.call_soon_threadsafe(self.task.cancel)

    def _run_thread(self):
        """Точка входа потока: создаёт event loop и запускает main()"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # Перенаправляем print через монки-патчинг
            self._patch_stdout()

            from main import main as parser_main
            self.task = self.loop.create_task(parser_main())
            self.loop.run_until_complete(self.task)

            self.status = "finished"
            self.log("[OK] Парсер завершил работу.")
        except asyncio.CancelledError:
            self.status = "finished"
            self.log("[!] Парсер остановлен пользователем.")
        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            self.log(f"[ERROR] {type(e).__name__}: {e}")
            import traceback
            for line in traceback.format_exc().splitlines():
                self.log(line)
        finally:
            self.finished_at = datetime.now()
            self._unpatch_stdout()
            if self.loop:
                self.loop.close()

    def _patch_stdout(self):
        """Перенаправляет stdout в логи раннера"""
        import sys
        self._orig_stdout = sys.stdout
        runner = self

        class _LogStream(io.TextIOBase):
            def __init__(self):
                self._buf = ""

            def write(self, s):
                if not s:
                    return 0
                self._buf += s
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    if line.strip():
                        runner.log(line.rstrip())
                # Дублируем в оригинальный stdout (для отладки)
                try:
                    runner._orig_stdout.write(s)
                except Exception:
                    pass
                return len(s)

            def flush(self):
                if self._buf.strip():
                    runner.log(self._buf.rstrip())
                    self._buf = ""
                try:
                    runner._orig_stdout.flush()
                except Exception:
                    pass

        sys.stdout = _LogStream()

    def _unpatch_stdout(self):
        """Восстанавливает оригинальный stdout"""
        import sys
        if hasattr(self, "_orig_stdout"):
            sys.stdout = self._orig_stdout


# Глобальный singleton
parser_runner = ParserRunner()
