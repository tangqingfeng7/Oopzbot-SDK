import json

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import rsa

from oopz import (
    ChannelGroupsResult,
    ChannelMessage,
    ChatMessageEvent,
    DailySpeechResult,
    MessageSendResult,
    OopzApiError,
    OopzAuthError,
    OopzClient,
    OopzConfig,
    OopzConnectionError,
    OopzRateLimitError,
    OopzSender,
    PersonDetail,
    PrivateSessionResult,
    SelfDetail,
    Signer,
    UploadResult,
    VoiceChannelMembersResult,
    __version__,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []
        self.sock = type("Sock", (), {"connected": True})()

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.sock.connected = False


def _make_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _make_config(**overrides) -> OopzConfig:
    config = OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=_make_private_key(),
        default_area="area",
        default_channel="channel",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_version_is_exposed() -> None:
    assert __version__ == "0.4.3"


def test_config_requires_private_key() -> None:
    with pytest.raises(ValueError):
        OopzConfig(
            device_id="device",
            person_uid="person",
            jwt_token="jwt",
            private_key=None,
        )


def test_signer_invalid_private_key_raises_auth_error() -> None:
    config = _make_config(private_key=object())

    with pytest.raises(OopzAuthError):
        Signer(config)


def test_sender_context_manager_closes_session(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    state = {"closed": False}

    def _close() -> None:
        state["closed"] = True

    monkeypatch.setattr(sender.session, "close", _close)

    with sender as managed_sender:
        assert managed_sender is sender

    assert state["closed"] is True


def test_send_message_returns_result_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    def _fake_post(url_path: str, body: dict):
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "msg-1"}},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.send_message("hello", auto_recall=False)

    assert isinstance(result, MessageSendResult)
    assert result.message_id == "msg-1"
    assert result.area == "area"
    assert result.channel == "channel"


def test_send_message_v2_builds_wrapped_payload(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"messageId": "msg-v2"}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.send_message_v2("hello", mentionList=["user-1"], auto_recall=False)

    assert captured["url_path"] == "/im/session/v2/sendGimMessage"
    assert captured["body"]["message"]["channel"] == "channel"
    assert captured["body"]["message"]["mentionList"] == [
        {"person": "user-1", "isBot": False, "botType": "", "offset": -1}
    ]
    assert "(met)user-1(met)" in captured["body"]["message"]["content"]
    assert result.message_id == "msg-v2"


def test_send_message_raises_rate_limit_error(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    def _fake_post(url_path: str, body: dict):
        return _FakeResponse(
            429,
            payload={"message": "请求过快"},
            headers={"Retry-After": "3"},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    with pytest.raises(OopzRateLimitError) as exc_info:
        sender.send_message("hello", auto_recall=False)

    assert exc_info.value.retry_after == 3
    assert exc_info.value.status_code == 429


def test_sender_get_translates_request_exception(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    def _raise(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(sender.session, "get", _raise)

    with pytest.raises(OopzConnectionError):
        sender._get("/userSubscribeArea/v1/list")


def test_send_private_message_returns_result_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender,
        "open_private_session",
        lambda target: PrivateSessionResult(channel="DM12345678901234567890"),
    )

    def _fake_post(url_path: str, body: dict):
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "dm-1"}},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.send_private_message("target-uid", "hello")

    assert isinstance(result, MessageSendResult)
    assert result.message_id == "dm-1"
    assert result.target == "target-uid"
    assert result.channel == "DM12345678901234567890"


def test_list_sessions_returns_dict_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(
            200,
            payload={"status": True, "data": [{"channel": "DM123", "lastTime": "123456"}]},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.list_sessions(last_time="123456")

    assert captured["url_path"] == "/im/session/v1/sessions"
    assert captured["body"] == {"lastTime": "123456"}
    assert result[0]["channel"] == "DM123"


def test_get_private_messages_returns_models(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "messages": [
                        {
                            "messageId": "dm-1",
                            "content": "hello",
                            "channel": "DM123",
                            "area": "",
                            "person": "user-1",
                        }
                    ]
                },
            },
        )

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_private_messages("DM123", size=20, before_message_id="dm-0")

    assert captured["url_path"] == "/im/session/v2/messageBefore"
    assert captured["params"] == {"area": "", "channel": "DM123", "size": "20", "messageId": "dm-0"}
    assert len(result) == 1
    assert isinstance(result[0], ChannelMessage)
    assert result[0].message_id == "dm-1"


def test_save_read_status_posts_expected_body(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.save_read_status("DM123", message_id="dm-1")

    assert captured["url_path"] == "/im/session/v1/saveReadStatus"
    assert captured["body"] == {
        "area": "",
        "status": [{"person": "person", "channel": "DM123", "messageId": "dm-1"}],
    }
    assert result.ok is True
    assert result.message == "已保存已读状态"


def test_get_system_message_unread_count_returns_int(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(200, payload={"status": True, "data": {"unreadCount": 7}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_system_message_unread_count()

    assert captured["url_path"] == "/im/systemMessage/v1/unreadCount"
    assert captured["params"] is None
    assert result == 7


def test_get_system_message_list_returns_dict_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"list": [{"id": "sys-1", "title": "系统通知"}]}},
        )

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_system_message_list(offset_time="123456")

    assert captured["url_path"] == "/im/systemMessage/v1/messageList"
    assert captured["params"] == {"offsetTime": "123456"}
    assert result == [{"id": "sys-1", "title": "系统通知"}]


def test_get_top_messages_returns_dict_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"topMessages": [{"messageId": "top-1"}]}},
        )

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_top_messages()

    assert captured["url_path"] == "/im/session/v2/topMessages"
    assert captured["params"] == {"area": "area", "channel": "channel"}
    assert result == [{"messageId": "top-1"}]


def test_get_areas_unread_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"area-1": 3}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.get_areas_unread(["area-1", ""])

    assert captured["url_path"] == "/im/session/v1/areasUnread"
    assert captured["body"] == {"areas": ["area-1"]}
    assert result == {"area-1": 3}


def test_get_areas_mention_unread_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"area-1": 1}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.get_areas_mention_unread(["area-1"])

    assert captured["url_path"] == "/im/session/v1/areasMentionUnread"
    assert captured["body"] == {"areas": ["area-1"]}
    assert result == {"area-1": 1}


def test_get_gim_reactions_returns_payload(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: list[dict]):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"reactions": []}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.get_gim_reactions([{"area": "area", "channel": "channel", "messageId": "msg-1"}])

    assert captured["url_path"] == "/im/session/v1/gimReactions"
    assert captured["body"] == [{"area": "area", "channel": "channel", "messageId": "msg-1"}]
    assert result["data"] == {"reactions": []}


def test_get_gim_message_details_returns_payload(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"messageId": "msg-1"}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.get_gim_message_details({"area": "area", "channel": "channel", "messageId": "msg-1"})

    assert captured["url_path"] == "/im/session/v1/gimMessageDetails"
    assert captured["body"] == {"area": "area", "channel": "channel", "messageId": "msg-1"}
    assert result["data"] == {"messageId": "msg-1"}


def test_upload_file_returns_upload_result(monkeypatch, tmp_path) -> None:
    sender = OopzSender(_make_config())
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"hello")

    monkeypatch.setattr(
        sender,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                },
            },
        ),
    )

    class _UploadResp:
        status_code = 200
        text = ""

    monkeypatch.setattr(sender.session, "put", lambda *args, **kwargs: _UploadResp())

    result = sender.upload_file(str(sample), file_type="IMAGE", ext=".bin")

    assert isinstance(result, UploadResult)
    assert result.attachment.file_key == "file-key"
    assert result.attachment.url == "https://cdn.example.com/file-key"


def test_get_area_members_returns_stale_cache_on_rate_limit(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    cache_key = ("area", 0, 49)
    sender._area_members_cache[cache_key] = {
        "ts": 10_000_000.0,
        "data": {"members": [{"uid": "u1", "online": 1}]},
    }

    monkeypatch.setattr("oopz.api.time.time", lambda: 10_000_010.0)
    monkeypatch.setattr("oopz.api.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(429, payload={"message": "too fast"}),
    )

    result = sender.get_area_members()

    assert result["stale"] is True
    assert result["rateLimited"] is True
    assert result["from_cache"] is True
    assert result["members"][0]["uid"] == "u1"


def test_get_area_channels_returns_cached_result_on_rate_limit(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    cached = ChannelGroupsResult(
        groups=[{"id": "group-1", "name": "分组", "channels": [{"id": "channel-1", "name": "大厅", "type": "TEXT"}]}],
        from_cache=False,
    )
    sender._set_cached_value(("area_channels", "area"), cached)

    monkeypatch.setattr("oopz.api.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(429, payload={"message": "busy"}),
    )

    result = sender.get_area_channels()

    assert isinstance(result, ChannelGroupsResult)
    assert result.from_cache is True
    assert result.groups[0]["id"] == "group-1"


def test_copy_channel_returns_operation_result(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"channel": "channel-copy-1"}},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)
    monkeypatch.setattr(sender, "_extract_channel_id", lambda payload: payload.get("channel") if isinstance(payload, dict) else None)

    result = sender.copy_channel("channel-1", name="复制频道")

    assert captured["url_path"] == "/area/v1/channel/v1/copy"
    assert captured["body"] == {"area": "area", "channel": "channel-1", "name": "复制频道"}
    assert result.ok is True
    assert result.payload["channel"] == "channel-copy-1"


def test_search_area_private_setting_members_returns_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"members": [{"uid": "u1", "name": "Alice"}]}},
        )

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.search_area_private_setting_members(keyword="Ali", page=2)

    assert captured["url_path"] == "/area/v3/search/areaPrivateSettingMembers"
    assert captured["params"] == {"area": "area", "keyword": "Ali", "page": "2"}
    assert result == [{"uid": "u1", "name": "Alice"}]


def test_get_self_detail_returns_cached_result_on_connection_error(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    sender._set_cached_value(
        ("self_detail", "person"),
        SelfDetail(uid="person", name="bot", from_cache=False, payload={"uid": "person", "name": "bot"}),
    )

    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: (_ for _ in ()).throw(OopzConnectionError("断线")),
    )
    monkeypatch.setattr("oopz.api.time.sleep", lambda *_: None)

    result = sender.get_self_detail()

    assert isinstance(result, SelfDetail)
    assert result.from_cache is True
    assert result.name == "bot"


def test_get_person_detail_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    monkeypatch.setattr(
        sender,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
        ),
    )

    result = sender.get_person_detail("u1")

    assert isinstance(result, PersonDetail)
    assert result.uid == "u1"
    assert result.name == "Alice"


def test_get_novice_guide_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(200, payload={"status": True, "data": {"finished": False}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_novice_guide()

    assert captured["url_path"] == "/client/v1/person/v1/noviceGuide"
    assert captured["params"] is None
    assert result == {"finished": False}


def test_get_notice_setting_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"newMessage": True}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_notice_setting()

    assert captured["url_path"] == "/person/v1/userNoticeSetting/noticeSetting"
    assert result == {"newMessage": True}


def test_get_user_remark_names_returns_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"userRemarkNames": [{"uid": "u1", "remarkName": "备注"}]}},
        )

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_user_remark_names("u1")

    assert captured["url_path"] == "/person/v1/remarkName/getUserRemarkNames"
    assert captured["params"] == {"uid": "u1"}
    assert result == [{"uid": "u1", "remarkName": "备注"}]


def test_check_block_status_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(200, payload={"status": True, "data": {"blocked": False}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.check_block_status("u2")

    assert captured["url_path"] == "/person/v1/blockCheck"
    assert captured["params"] == {"targetUid": "u2"}
    assert result == {"blocked": False}


def test_get_privacy_settings_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"everyoneAdd": True}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_privacy_settings()

    assert captured["url_path"] == "/client/v1/person/v1/privacy/v1/query"
    assert result == {"everyoneAdd": True}


def test_get_notification_settings_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"pushEnabled": True}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_notification_settings()

    assert captured["url_path"] == "/client/v1/person/v1/notification/v1/query"
    assert result == {"pushEnabled": True}


def test_get_real_name_auth_status_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"authState": 1}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_real_name_auth_status()

    assert captured["url_path"] == "/client/v1/person/v2/realNameAuth"
    assert result == {"authState": 1}


def test_get_friend_list_returns_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"friends": [{"uid": "u1", "name": "Alice"}]}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_friend_list()

    assert captured["url_path"] == "/client/v1/list/v1/friendship"
    assert result == [{"uid": "u1", "name": "Alice"}]


def test_get_blocked_list_returns_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"blocks": [{"uid": "u2", "name": "Bob"}]}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_blocked_list()

    assert captured["url_path"] == "/client/v1/list/v1/blocked"
    assert result == [{"uid": "u2", "name": "Bob"}]


def test_get_friend_requests_returns_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"requests": [{"uid": "u3", "direction": "IN"}]}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_friend_requests()

    assert captured["url_path"] == "/client/v1/friendship/v1/requests"
    assert result == [{"uid": "u3", "direction": "IN"}]


def test_get_diamond_remain_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(200, payload={"status": True, "data": {"remain": 12}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_diamond_remain()

    assert captured["url_path"] == "/diamond/v1/remain"
    assert result == {"remain": 12}


def test_get_mixer_settings_parses_json_string(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        return _FakeResponse(
            200,
            payload={
                "status": True,
                "data": '{"isFreeSpeech": true, "echoCancellation": true, "noiseSuppression": true}',
            },
        )

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_mixer_settings()

    assert captured["url_path"] == "/client/v1/settings/v1/mixer"
    assert result == {"isFreeSpeech": True, "echoCancellation": True, "noiseSuppression": True}


def test_set_user_remark_name_posts_expected_body(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.set_user_remark_name("u1", "新备注")

    assert captured["url_path"] == "/person/v1/remarkName/setUserRemarkName"
    assert captured["body"] == {"remarkUid": "u1", "remarkName": "新备注"}
    assert result.ok is True
    assert result.message == "已设置备注名"


def test_send_friend_request_posts_expected_body(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.send_friend_request("u2")

    assert captured["url_path"] == "/friendship/v1/request"
    assert captured["body"] == {"target": "u2"}
    assert result.ok is True
    assert result.message == "已发送好友申请"


def test_respond_friend_request_posts_expected_body(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.respond_friend_request("u3", agree=True, friend_request_id="req-1")

    assert captured["url_path"] == "/friendship/v1/response"
    assert captured["body"] == {"target": "u3", "agree": True, "friendRequestId": "req-1"}
    assert result.ok is True
    assert result.message == "已同意好友申请"


def test_remove_friend_calls_delete_with_query(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_delete(url_path: str, body=None):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_delete", _fake_delete)

    result = sender.remove_friend("u4")

    assert captured["url_path"] == "/friendship/v1/remove?target=u4"
    assert captured["body"] is None
    assert result.ok is True
    assert result.message == "已删除好友"


def test_edit_privacy_settings_patches_expected_body(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_patch(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_patch", _fake_patch)

    result = sender.edit_privacy_settings(
        everyone_add=True,
        with_friend_add=False,
        area_member_add=True,
        not_friend_chat=False,
    )

    assert captured["url_path"] == "/person/v1/privacy/v1/edit"
    assert captured["body"] == {
        "areaMemberAdd": True,
        "notFriendChat": False,
        "everyoneAdd": True,
        "withFriendAdd": False,
        "uid": "person",
    }
    assert result.ok is True
    assert result.message == "已更新隐私设置"


def test_edit_notification_settings_patches_expected_body(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_patch(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": True})

    monkeypatch.setattr(sender, "_patch", _fake_patch)

    result = sender.edit_notification_settings({"pushEnabled": True, "sound": False}, mobile=True)

    assert captured["url_path"] == "/person/v1/notification/v1/mobileEdit"
    assert captured["body"] == {"pushEnabled": True, "sound": False}
    assert result.ok is True
    assert result.message == "已更新通知设置"


def test_get_voice_channel_members_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    monkeypatch.setattr(
        sender,
        "_get_voice_channel_ids",
        lambda area: ["voice-1"],
    )
    monkeypatch.setattr(
        sender,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"channelMembers": {"voice-1": [{"uid": "u1", "name": "Alice"}]}}},
        ),
    )

    result = sender.get_voice_channel_members()

    assert isinstance(result, VoiceChannelMembersResult)
    assert result.channels["voice-1"][0]["uid"] == "u1"


def test_get_daily_speech_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": {"words": "今日宜写代码", "author": "Codex"}},
        ),
    )

    result = sender.get_daily_speech()

    assert isinstance(result, DailySpeechResult)
    assert result.words == "今日宜写代码"


def test_get_channel_messages_returns_models(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "messages": [
                        {
                            "messageId": "msg-1",
                            "content": "hello",
                            "area": "area-1",
                            "channel": "channel-1",
                            "person": "user-1",
                        }
                    ]
                },
            },
        ),
    )

    result = sender.get_channel_messages()

    assert len(result) == 1
    assert isinstance(result[0], ChannelMessage)
    assert result[0].message_id == "msg-1"
    assert result[0].content == "hello"


def test_get_channel_messages_raises_api_error_on_business_failure(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": False, "message": "业务失败"},
        ),
    )

    with pytest.raises(OopzApiError):
        sender.get_channel_messages()


def test_client_emits_typed_chat_event_and_auth_lifecycle() -> None:
    chat_events: list[ChatMessageEvent] = []
    lifecycle_states: list[str] = []
    client = OopzClient(
        _make_config(),
        on_chat_message=chat_events.append,
        on_lifecycle_event=lambda event: lifecycle_states.append(event.state),
    )

    ws = _FakeWebSocket()
    client._running = True
    client._on_open(ws)
    client._on_message(
        ws,
        json.dumps(
            {
                "event": 253,
                "body": json.dumps({"status": True, "code": 0}),
            }
        ),
    )
    client._on_message(
        ws,
        json.dumps(
            {
                "event": 9,
                "body": json.dumps(
                    {
                        "data": {
                            "messageId": "msg-1",
                            "person": "other",
                            "channel": "channel-1",
                            "area": "area-1",
                            "content": "hello",
                        }
                    }
                ),
            }
        ),
    )
    client.stop()

    assert "connected" in lifecycle_states
    assert "auth_sent" in lifecycle_states
    assert "auth_ok" in lifecycle_states
    assert len(chat_events) == 1
    assert chat_events[0].content == "hello"
    assert chat_events[0].message_id == "msg-1"


def test_client_emits_auth_failed_and_closes_socket() -> None:
    lifecycle = []
    client = OopzClient(
        _make_config(),
        on_lifecycle_event=lambda event: lifecycle.append((event.state, event.reason)),
    )

    ws = _FakeWebSocket()
    client._on_message(
        ws,
        json.dumps(
            {
                "event": 253,
                "body": json.dumps({"status": False, "code": 401, "message": "token 失效"}),
            }
        ),
    )

    assert ("auth_failed", "token 失效") in lifecycle
    assert ws.sock.connected is False
