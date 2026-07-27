"""
review_db.client — 后台 daemon-thread writer + 进程内单例 fire-and-forget 入库

关键设计:
- ReviewDbClient.start() 启动 1 个 daemon thread, 该 thread 全生命周期内维持
  一个 PyMySQL Connection (避免每条 insert 开 TCP 握手).
- 所有 record_*() 方法走 queue.put_nowait(...), 入队后立即返回 — 调用方不阻塞.
- Worker 在 shutdown(timeout) 时 flush 队列后退出.
- 异常处理: OperationalError 自动重连; 其他异常重试 3 次后丢日志, 绝不阻塞流水线.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from .config import ReviewDbConfig
from .schema import (
    UPSERT_ANALYSIS_REPORT_SQL,
    UPSERT_EVIDENCE_SQL,
    UPSERT_EVOLUTION_CHANGE_SQL,
    UPSERT_EVOLUTION_CHANGE_SEEDED_SQL,
    UPSERT_RUN_SESSION_SQL,
)

_logger = logging.getLogger(__name__)


class _Op(Enum):
    RUN_SESSION = "RUN_SESSION"
    ANALYSIS_REPORT = "ANALYSIS_REPORT"
    EVIDENCE = "EVIDENCE"
    EVOLUTION_CHANGE = "EVOLUTION_CHANGE"
    EVOLUTION_CHANGE_SEEDED = "EVOLUTION_CHANGE_SEEDED"


@dataclass
class _Task:
    op: _Op
    args: tuple
    enqueued_at: float


class ReviewDbClient:
    """进程内单例; 通过 core.review_db.get_client() 获取."""

    def __init__(self, cfg: ReviewDbConfig):
        self._cfg = cfg
        self._q: "queue.Queue[Optional[_Task]]" = queue.Queue(maxsize=cfg.queue_maxsize)
        self._stop = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._conn = None              # PyMySQL Connection (worker lifetime)
        self._retries = 3
        # atexit 注册: 进程退出时尽量 flush
        import atexit
        atexit.register(self._atexit_shutdown)

    # ---------- lifecycle ----------

    def start(self) -> None:
        if self._worker is not None:
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="review_db_worker",
            daemon=True,
        )
        self._worker.start()
        _logger.debug("review_db worker started")

    def shutdown(self, timeout: float = 10.0) -> None:
        """flush + signal stop + join. 多次调用安全."""
        if self._worker is None:
            return
        # 先 flush 已有队列
        try:
            self.flush(timeout=timeout)
        except Exception:
            pass
        # 用 None 作为"退出哨兵"提示 worker
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass
        self._stop.set()
        self._worker.join(timeout=timeout)
        self._close_conn()
        self._worker = None
        _logger.debug("review_db worker shut down")

    def _atexit_shutdown(self) -> None:
        """进程退出时 (含 KeyboardInterrupt) 的兜底 flush."""
        try:
            self.shutdown(timeout=2.0)
        except Exception:
            pass

    def flush(self, timeout: float = 5.0) -> bool:
        """阻塞等队列清空. 返回 True=已空."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._q.empty():
                return True
            time.sleep(0.05)
        return self._q.empty()

    # ---------- public record_* ----------

    def record_run_session(
        self,
        run_id: str,
        session_id: str,
        agent_cwd: Any,
        by_agent_type: Any,
        summary: Any,
        index_raw: Any,
    ) -> None:
        self._enqueue(_Task(
            op=_Op.RUN_SESSION,
            args=(run_id, session_id, agent_cwd, by_agent_type, summary, index_raw),
            enqueued_at=time.time(),
        ))

    def record_analysis_report(
        self,
        run_id: str,
        session_id: str,
        subject_target: str,
        suggestions_json: Any,
    ) -> None:
        self._enqueue(_Task(
            op=_Op.ANALYSIS_REPORT,
            args=(run_id, session_id, subject_target, suggestions_json),
            enqueued_at=time.time(),
        ))

    def record_evidence(
        self,
        session_id: str,
        uuid: str,
        detail_dict: dict,
    ) -> None:
        self._enqueue(_Task(
            op=_Op.EVIDENCE,
            args=(session_id, uuid, detail_dict),
            enqueued_at=time.time(),
        ))

    def record_evolution_change(
        self,
        run_id: str,
        subject_target: str,
        original_content: str,
        new_content: str,
        suggestions_json: Any,
        linediff_json: Any = None,
    ) -> None:
        self._enqueue(_Task(
            op=_Op.EVOLUTION_CHANGE,
            args=(
                run_id, subject_target, original_content, new_content,
                suggestions_json, linediff_json,
            ),
            enqueued_at=time.time(),
        ))

    def record_evolution_change_seeded(
        self,
        run_id: str,
        subject_target: str,
        suggestions_json: Any,
    ) -> None:
        """
        阶段 3 evolve-discovery 时机入库: 先写 (subject_target + suggestions_json),
        original_content / new_content 留空, 等 finalize 阶段补齐.
        同一 (run_id, subject_target) finalize 后会 UPSERT 更新这两个字段,
        因此允许先写占位行.
        """
        self._enqueue(_Task(
            op=_Op.EVOLUTION_CHANGE_SEEDED,
            args=(run_id, subject_target, suggestions_json),
            enqueued_at=time.time(),
        ))

    # ---------- worker internals ----------

    def _enqueue(self, task: _Task) -> None:
        """非阻塞入队. 队列满则丢日志 (主线程不阻塞)."""
        try:
            self._q.put_nowait(task)
        except queue.Full:
            _logger.warning(
                "review_db queue full (size=%d), dropped task %s",
                self._cfg.queue_maxsize, task.op.value,
            )

    def _worker_loop(self) -> None:
        while True:
            task = self._q.get()
            if task is None or self._stop.is_set():
                self._q.task_done()
                return
            try:
                self._execute(task)
            except Exception as e:  # 不让单个 task 拖垮 worker
                _logger.warning(
                    "review_db task %s fatal error: %s",
                    task.op.value, e, exc_info=True,
                )
            finally:
                self._q.task_done()

    def _execute(self, task: _Task) -> None:
        """dispatch + 3 次重试 + OperationalError 自动重连."""
        last_err: Optional[Exception] = None
        for attempt in range(self._retries):
            try:
                self._dispatch(task)
                return
            except Exception as e:
                last_err = e
                _logger.debug(
                    "review_db attempt %d/%d failed for %s: %s",
                    attempt + 1, self._retries, task.op.value, e,
                )
                # 若是连接类错误, 重置连接
                try:
                    import pymysql  # noqa: F401
                    if isinstance(e, pymysql.err.OperationalError):
                        self._close_conn()
                except Exception:
                    pass
                time.sleep(0.2 * (attempt + 1))  # backoff
        _logger.warning(
            "review_db task %s gave up after %d retries: %s",
            task.op.value, self._retries, last_err,
        )

    def _dispatch(self, task: _Task) -> None:
        conn = self._ensure_conn()
        params = self._encode_params(task)
        with conn.cursor() as cur:
            sql = self._sql_for(task.op)
            cur.execute(sql, params)
            conn.commit()

    def _encode_params(self, task: _Task) -> tuple:
        """所有 JSON-shaped 字段先 dumps 成字符串, 因为 PyMySQL 的 %s 与 JSON 类型不互通."""
        if task.op is _Op.RUN_SESSION:
            _r, sid, cwd, by, summary, raw = task.args
            return (
                _r, sid,
                json.dumps(cwd, ensure_ascii=False) if cwd is not None else None,
                json.dumps(by, ensure_ascii=False) if by is not None else None,
                json.dumps(summary, ensure_ascii=False) if summary is not None else None,
                json.dumps(raw, ensure_ascii=False) if raw is not None else None,
            )
        if task.op is _Op.ANALYSIS_REPORT:
            _r, sid, st, sjson = task.args
            return (
                _r, sid, st,
                json.dumps(sjson, ensure_ascii=False)
                if not isinstance(sjson, str) else sjson,
            )
        if task.op is _Op.EVIDENCE:
            sid, uuid, detail = task.args
            return (sid, uuid, json.dumps(detail, ensure_ascii=False))
        if task.op is _Op.EVOLUTION_CHANGE_SEEDED:
            _r, st, sjson = task.args
            return (
                _r, st, "",
                json.dumps(sjson, ensure_ascii=False)
                if not isinstance(sjson, str) else sjson,
            )
        if task.op is _Op.EVOLUTION_CHANGE:
            _r, st, orig, new, sjson, ldiff = task.args
            return (
                _r, st, orig, new,
                json.dumps(sjson, ensure_ascii=False)
                if not isinstance(sjson, str) else sjson,
                json.dumps(ldiff, ensure_ascii=False)
                if ldiff is not None else None,
            )
        raise RuntimeError(f"unknown op {task.op}")

    def _sql_for(self, op: _Op) -> str:
        return {
            _Op.RUN_SESSION:        UPSERT_RUN_SESSION_SQL,
            _Op.ANALYSIS_REPORT:    UPSERT_ANALYSIS_REPORT_SQL,
            _Op.EVIDENCE:           UPSERT_EVIDENCE_SQL,
            _Op.EVOLUTION_CHANGE:         UPSERT_EVOLUTION_CHANGE_SQL,
            _Op.EVOLUTION_CHANGE_SEEDED:  UPSERT_EVOLUTION_CHANGE_SEEDED_SQL,
        }[op]

    def _ensure_conn(self):
        if self._conn is not None:
            try:
                self._conn.ping(reconnect=True)
                return self._conn
            except Exception:
                self._close_conn()
        import pymysql
        self._conn = pymysql.connect(
            host=self._cfg.host,
            port=self._cfg.port,
            user=self._cfg.user,
            password=self._cfg.password,
            database=self._cfg.database,
            charset="utf8mb4",
            autocommit=False,
        )
        _logger.debug(
            "review_db worker connected to mysql %s:%d/%s",
            self._cfg.host, self._cfg.port, self._cfg.database,
        )
        return self._conn

    def _close_conn(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = None
