# Media Service

入口：`client.media` 或 `bot.media`。

## `upload_file(file, file_type, ext, animated=False)`

上传本地文件，返回上传结果模型。

```python
uploaded = await client.media.upload_file(
    file="./demo.png",
    file_type="IMAGE",
    ext="png",
)
print(uploaded.file_key, uploaded.url)
```

| 参数 | 说明 |
| --- | --- |
| `file` | 本地文件路径。 |
| `file_type` | 文件类型，例如 `IMAGE`、`FILE`、`AUDIO`。 |
| `ext` | 文件扩展名，不带点，例如 `png`。 |
| `animated` | 是否动画图片或动态资源。 |

内部流程：

1. 请求 `/rtc/v1/cos/v1/signedUploadUrl` 获取上传 ticket。
2. 读取本地文件 bytes。
3. PUT 到签名上传 URL。
4. 构造 `UploadedFileResult`。

## 与消息发送配合

推荐图片消息使用 `Image.from_file()`，它会自动调用上传逻辑：

```python
from oopz_sdk.models.segment import Image

await bot.messages.send_message(
    Image.from_file("./demo.png"),
    area=area,
    channel=channel,
)
```

如果你需要提前上传并复用附件，可以先调用 `upload_file()`。
