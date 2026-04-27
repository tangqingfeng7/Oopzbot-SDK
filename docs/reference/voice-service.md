# Voice Service

入口：`bot.voice`。语音服务依赖 `bot.channels` 进入语音频道，并使用 Playwright 浏览器后端加入 Agora 房间和推流。

## 准备

```bash
python -m playwright install chromium
```

配置示例：

```python
config = OopzConfig(
    ...,
    voice_backend="browser",
    voice_browser_headless=True,
)
```

## 方法列表

| 方法 | 说明 |
| --- | --- |
| `start()` | 启动浏览器语音后端。通常 `join()` 前会由业务显式调用或在示例中调用。 |
| `join(area, channel, from_area="", from_channel="", rtc_uid=None)` | 进入 Oopz 语音频道并加入 Agora 房间。 |
| `leave()` | 离开 Agora 和 Oopz 语音频道。 |
| `play_url(url)` | 播放网络音频 URL。 |
| `play_file(file_path, mime_type=None)` | 播放本地音频文件。 |
| `play_bytes(data, mime_type="audio/mpeg")` | 播放内存中的音频 bytes。 |
| `stop()` | 停止当前播放。 |
| `pause()` | 暂停。 |
| `resume()` | 恢复。 |
| `seek(seconds)` | 跳转播放位置。 |
| `set_volume(volume)` | 设置音量。 |
| `get_state()` | 获取播放状态。 |
| `get_current_time()` | 获取当前播放时间。 |
| `close()` | 关闭语音后端。 |

## 加入并播放本地文件

```python
await bot.voice.start()
await bot.voice.join(area="域 ID", channel="语音频道 ID")
await bot.voice.play_file("./demo.mp3")
```

播放完成后如果希望机器人离开频道：

```python
await bot.voice.leave()
```

`play_file()` 只负责播放音频，不会自动离开语音频道。是否保持在频道内由业务决定。

## RTC UID

`join(..., rtc_uid=...)` 的 `rtc_uid` 必须是整数或可转换为整数的字符串。SDK 会在进入服务端频道前校验，避免服务端已记录进入语音频道后浏览器侧才失败，造成残留状态。

## 失败清理

`join()` 在以下情况会尝试回滚：

- `enter_channel()` 返回缺失 `rtc_token` 或 `rtc_channel_name`。
- 浏览器后端加入 Agora 失败。
- 身份绑定桥接首次发送失败。

回滚包括：

1. `backend.leave()`
2. `channels.leave_voice_channel()`

## 属性

| 属性 | 说明 |
| --- | --- |
| `agora_uid` | 浏览器后端生成或使用的 Agora UID。 |
| `current_sign` | 当前语音频道的 `ChannelSign`，未加入时为 `None`。 |
