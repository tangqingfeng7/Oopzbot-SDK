from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, TypedDict


JsonDict = dict[str, Any]
DetailType = Literal["private", "channel", "group"]


class OneBotSelf(TypedDict):
    platform: str
    user_id: str


class ActionResponse(TypedDict, total=False):
    status: str
    retcode: int
    data: Any
    message: str
    echo: Any


@dataclass(slots=True)
class SendParts:
    parts: list[Any]
    mention_list: list[dict[str, Any]]
    is_mention_all: bool
    reference_message_id: str | None


@dataclass(slots=True)
class MessageRecord:
    """
    OneBot 内部 message_id -> Oopz 原始消息定位信息。

    Oopz 撤回需要：
    - 频道：area + channel + message_id
    - 私聊：target/channel + message_id

    所以 OneBot 侧不要直接暴露 Oopz messageId，
    而是暴露一个内部 ID，再通过 SQLite 找回上下文。
    """

    ob_message_id: str
    oopz_message_id: str
    detail_type: str

    area: str = ""
    channel: str = ""
    target: str = ""
    user_id: str = ""

    created_at: float = 0.0
    raw: dict[str, Any] | None = None


class MessageStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            base = Path.cwd() / ".oopz_sdk"
            base.mkdir(parents=True, exist_ok=True)
            db_path = base / "onebot_v12_message_map.sqlite3"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_map (
                    ob_message_id TEXT PRIMARY KEY,
                    oopz_message_id TEXT NOT NULL,
                    detail_type TEXT NOT NULL,

                    area TEXT NOT NULL DEFAULT '',
                    channel TEXT NOT NULL DEFAULT '',
                    target TEXT NOT NULL DEFAULT '',
                    user_id TEXT NOT NULL DEFAULT '',

                    created_at REAL NOT NULL,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_message_map_oopz
                ON message_map(oopz_message_id, detail_type, area, channel, target)
                """
            )
            conn.commit()

    def save(self, record: MessageRecord) -> MessageRecord:
        if not record.created_at:
            record.created_at = time.time()

        raw_json = json.dumps(record.raw or {}, ensure_ascii=False)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO message_map (
                    ob_message_id,
                    oopz_message_id,
                    detail_type,
                    area,
                    channel,
                    target,
                    user_id,
                    created_at,
                    raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ob_message_id) DO UPDATE SET
                    oopz_message_id = excluded.oopz_message_id,
                    detail_type = excluded.detail_type,
                    area = excluded.area,
                    channel = excluded.channel,
                    target = excluded.target,
                    user_id = excluded.user_id,
                    raw_json = excluded.raw_json
                """,
                (
                    record.ob_message_id,
                    record.oopz_message_id,
                    record.detail_type,
                    record.area,
                    record.channel,
                    record.target,
                    record.user_id,
                    record.created_at,
                    raw_json,
                ),
            )
            conn.commit()

        return record

    def get(self, ob_message_id: str) -> MessageRecord | None:
        ob_message_id = str(ob_message_id or "")
        if not ob_message_id:
            return None

        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM message_map
                WHERE ob_message_id = ?
                """,
                (ob_message_id,),
            ).fetchone()

        if row is None:
            return None

        try:
            raw = json.loads(row["raw_json"] or "{}")
        except json.JSONDecodeError:
            raw = {}

        return MessageRecord(
            ob_message_id=row["ob_message_id"],
            oopz_message_id=row["oopz_message_id"],
            detail_type=row["detail_type"],
            area=row["area"],
            channel=row["channel"],
            target=row["target"],
            user_id=row["user_id"],
            created_at=float(row["created_at"] or 0),
            raw=raw,
        )

    def cleanup(self, older_than_seconds: int = 7 * 24 * 3600) -> int:
        threshold = time.time() - older_than_seconds
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM message_map
                WHERE created_at < ?
                """,
                (threshold,),
            )
            conn.commit()
            return int(cur.rowcount or 0)


def make_ob_message_id(
    *,
    oopz_message_id: str,
    detail_type: str,
    area: str = "",
    channel: str = "",
    target: str = "",
    user_id: str = "",
) -> str:
    """
    用上下文生成 OneBot 内部 ID，避免 Oopz messageId 非全局唯一。
    """
    source = "|".join(
        [
            detail_type,
            str(oopz_message_id or ""),
            str(area or ""),
            str(channel or ""),
            str(target or ""),
            str(user_id or ""),
        ]
    )
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()
    return f"oopz:{digest[:24]}"


def parse_oopz_timestamp(value: str | int | float | None) -> float:
    """
    Oopz timestamp 是 Unix epoch microseconds。
    返回 OneBot v12 需要的秒级 float timestamp。
    """

    if value is None:
        return time.time()

    text = str(value).strip()
    if not text:
        return time.time()

    try:
        return int(text) / 1_000_000
    except ValueError:
        return time.time()


def ok(data: Any = None, *, echo: Any = None) -> ActionResponse:
    resp: ActionResponse = {
        "status": "ok",
        "retcode": 0,
        "data": data,
        "message": "",
    }
    if echo is not None:
        resp["echo"] = echo
    return resp


def failed(retcode: int, message: str, *, echo: Any = None) -> ActionResponse:
    resp: ActionResponse = {
        "status": "failed",
        "retcode": retcode,
        "data": None,
        "message": message,
    }
    if echo is not None:
        resp["echo"] = echo
    return resp


def require_str(data: Mapping[str, Any], key: str) -> str:
    value = str(data.get(key) or "")
    if not value:
        raise ValueError(f"{key} is required")
    return value