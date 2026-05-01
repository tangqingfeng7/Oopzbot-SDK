from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oopz_sdk.client.bot import OopzBot


def install_onebot(bot: OopzBot) -> None:
    """
    根据 bot.config 安装 OneBot v11/v12 适配器。

    这个文件是 OneBot 与 OopzBot 的装配层：
    - OopzBot 不直接知道 v11/v12 的 Adapter/Server/ServerConfig；
    - OneBot Adapter 仍然只负责协议转换和 action；
    - OneBot Server 仍然只负责 HTTP/WS/webhook/reverse WS 连接层。
    """
    install_onebot_v11(bot)
    # todo v12 的实现还未经测试
    # install_onebot_v12(bot)


def install_onebot_v11(bot: OopzBot) -> Any | None:
    config = getattr(bot.config, "onebot_v11", None)
    if config is None or not getattr(config, "enabled", False):
        return None

    from oopz_sdk.adapters.onebot.v11 import (
        OneBotV11Adapter,
        OneBotV11Server,
        OneBotV11ServerConfig,
    )

    adapter = OneBotV11Adapter(
        bot,
        platform=getattr(config, "platform", "oopz"),
        self_id=getattr(config, "self_id", "") or bot.config.person_uid,
        db_path=getattr(config, "db_path", None),
    )

    server = None
    if getattr(config, "auto_start_server", True):
        server_config = OneBotV11ServerConfig(
            host=getattr(config, "host", "127.0.0.1"),
            port=getattr(config, "port", 6700),
            access_token=getattr(config, "access_token", ""),
            enable_http=getattr(config, "enable_http", True),
            enable_ws=getattr(config, "enable_ws", True),
            webhook_urls=list(getattr(config, "webhook_urls", []) or []),
            ws_reverse_urls=list(getattr(config, "ws_reverse_urls", []) or []),
            ws_reverse_reconnect_interval=getattr(
                config,
                "ws_reverse_reconnect_interval",
                3.0,
            ),
            send_connect_event=getattr(config, "send_connect_event", True),
        )
        server = OneBotV11Server(adapter, server_config)

    bot.add_adapter(adapter, server=server)
    return adapter


def install_onebot_v12(bot: OopzBot) -> Any | None:
    config = getattr(bot.config, "onebot_v12", None)
    if config is None or not getattr(config, "enabled", False):
        return None

    from oopz_sdk.adapters.onebot.v12 import (
        OneBotV12Adapter,
        OneBotV12Server,
        OneBotV12ServerConfig,
    )

    adapter = OneBotV12Adapter(
        bot,
        platform=getattr(config, "platform", "oopz"),
        self_id=getattr(config, "self_id", "") or bot.config.person_uid,
        db_path=getattr(config, "db_path", None),
    )

    server = None
    if getattr(config, "auto_start_server", True):
        server_config = OneBotV12ServerConfig(
            host=getattr(config, "host", "127.0.0.1"),
            port=getattr(config, "port", 6727),
            access_token=getattr(config, "access_token", ""),
            enable_http=getattr(config, "enable_http", True),
            enable_ws=getattr(config, "enable_ws", True),
            webhook_urls=list(getattr(config, "webhook_urls", []) or []),
            ws_reverse_urls=list(getattr(config, "ws_reverse_urls", []) or []),
            ws_reverse_reconnect_interval=getattr(
                config,
                "ws_reverse_reconnect_interval",
                3.0,
            ),
            send_connect_event=getattr(config, "send_connect_event", True),
        )
        server = OneBotV12Server(adapter, server_config)

    bot.add_adapter(adapter, server=server)
    return adapter
