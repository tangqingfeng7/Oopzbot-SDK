from __future__ import annotations

import random
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

JsonDict = dict[str, Any]
ActionResponse = dict[str, Any]


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


def require_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if value is None or value == "":
        raise ValueError(f"{key} is required")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer") from None


@dataclass(slots=True, frozen=True)
class OneBotId:
    """
    onebots 风格 ID 对象。

    string/source 保存平台原始 ID 或复合 source；number 是 OneBot v11 对外暴露的数字 ID。
    """

    string: str
    number: int
    source: str


class IdStore:
    """
    OneBot v11 数字 ID 映射表。

    行为接近 onebots 的 createId / resolveId：
    - number 原样返回；
    - string 先查 SQLite；
    - 不存在则随机生成一个稳定保存的数字 ID；
    - resolveId(number) 反查原始 source。
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            base = Path.cwd() / ".oopz_sdk"
            base.mkdir(parents=True, exist_ok=True)
            db_path = base / "onebot_v11_id_map.sqlite3"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS onebot_v11_id_map (
                    string TEXT NOT NULL UNIQUE,
                    number INTEGER NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_onebot_v11_id_map_number
                ON onebot_v11_id_map(number)
                """
            )

    def create_id(self, raw_id: str | int) -> OneBotId:
        if isinstance(raw_id, int):
            return OneBotId(string=str(raw_id), number=raw_id, source=str(raw_id))

        source = str(raw_id or "")
        if not source:
            raise ValueError("raw_id is required")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT string, number, source
                FROM onebot_v11_id_map
                WHERE string = ?
                """,
                (source,),
            ).fetchone()

            if row is not None:
                return OneBotId(string=str(row[0]), number=int(row[1]), source=str(row[2]))

            number = self._new_unique_number(conn)
            conn.execute(
                """
                INSERT INTO onebot_v11_id_map(string, number, source, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (source, number, source, int(time.time())),
            )
            return OneBotId(string=source, number=number, source=source)

    def createId(self, raw_id: str | int) -> OneBotId:
        """onebots 风格 camelCase 别名。"""
        return self.create_id(raw_id)

    def resolve_id(self, number: int | str) -> OneBotId:
        try:
            numeric_id = int(number)
        except (TypeError, ValueError):
            raise ValueError(f"invalid onebot v11 numeric id: {number!r}") from None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT string, number, source
                FROM onebot_v11_id_map
                WHERE number = ?
                """,
                (numeric_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"unknown onebot v11 id: {numeric_id}")

        return OneBotId(string=str(row[0]), number=int(row[1]), source=str(row[2]))

    def resolveId(self, number: int | str) -> OneBotId:
        """onebots 风格 camelCase 别名。"""
        return self.resolve_id(number)

    def try_resolve_id(self, number: int | str) -> OneBotId | None:
        try:
            return self.resolve_id(number)
        except (ValueError, KeyError):
            return None

    def _new_unique_number(self, conn: sqlite3.Connection) -> int:
        # onebots 是随机数字；这里限制在 JS 安全整数内，避免 Web/JS 客户端丢精度。
        for _ in range(100):
            number = random.randint(10_000_000, 100_000_000_000)
            row = conn.execute(
                "SELECT 1 FROM onebot_v11_id_map WHERE number = ?",
                (number,),
            ).fetchone()
            if row is None:
                return number
        raise RuntimeError("failed to allocate onebot v11 id")


def make_user_source(uid: str) -> str:
    return f"user:{uid}"


def parse_user_source(source: str) -> str:
    prefix = "user:"
    if source.startswith(prefix):
        return source.removeprefix(prefix)
    return source


def make_self_source(uid: str) -> str:
    return f"self:{uid}"


def make_group_source(*, area: str, channel: str) -> str:
    # v11 group_id 映射到 Oopz channel；area 也参与 source，避免跨 area 冲突。
    return f"group:{area}:{channel}"


def parse_group_source(source: str) -> tuple[str, str]:
    prefix = "group:"
    if not source.startswith(prefix):
        raise ValueError(f"invalid group source: {source!r}")

    rest = source.removeprefix(prefix)
    area, sep, channel = rest.partition(":")
    if not sep or not area or not channel:
        raise ValueError(f"invalid group source: {source!r}")
    return area, channel


def make_message_source(
    *,
    area: str = "",
    channel: str = "",
    target: str = "",
    message_id: str,
) -> str:
    return f"message:{area}:{channel}:{target}:{message_id}"


def parse_message_source(source: str) -> tuple[str, str, str, str]:
    prefix = "message:"
    if not source.startswith(prefix):
        raise ValueError(f"invalid message source: {source!r}")

    rest = source.removeprefix(prefix)
    parts = rest.split(":", 3)
    if len(parts) != 4:
        raise ValueError(f"invalid message source: {source!r}")
    area, channel, target, message_id = parts
    if not message_id:
        raise ValueError(f"invalid message source: {source!r}")
    return area, channel, target, message_id


def parse_oopz_timestamp(value: str | int | float | None) -> int:
    if value is None:
        return int(time.time())

    text = str(value).strip()
    if not text:
        return int(time.time())

    try:
        num = int(text)
    except ValueError:
        return int(time.time())

    if num > 10_000_000_000_000:
        return int(num / 1_000_000)
    if num > 10_000_000_000:
        return int(num / 1_000)
    return int(num)
