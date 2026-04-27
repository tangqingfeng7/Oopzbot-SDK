# Media Service

`Media Service` 用于上传本地文件，并生成可用于消息附件或 Segment 消息的上传结果。

---

## `upload_file(file, file_type, ext, animated=False)`

上传本地文件，并返回 `UploadedFileResult`。

!!! warning "提示"
    目前Oopz平台仅支持图片上传，`file_type` 需要传 `IMAGE`。

```python
uploaded = await client.media.upload_file(
    file="./demo.png",
    file_type="IMAGE",
    ext="png",
)

print(uploaded.file_key)
print(uploaded.url)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `file` | `str` | 是 | - | 本地文件路径。SDK 会读取该路径对应的文件 bytes。 |
    | `file_type` | `str` | 是 | - | 文件类型，例如 `IMAGE`、`FILE`、`AUDIO`。当前图片消息主要使用 `IMAGE`。 |
    | `ext` | `str` | 是 | - | 文件扩展名，例如 `png`、`jpg`、`.png`。该值会原样传给上传 ticket 接口。 |
    | `animated` | `bool` | 否 | `False` | 是否为动画图片或动态资源。 |

=== "返回值"

    返回：`UploadedFileResult`。

    对应模型：`oopz_sdk.models.UploadedFileResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `file_key` | `str` | `""` | 上传后的文件 key。发送图片消息时会放进图片占位文本或附件信息中。 |
    | `url` | `str` | `""` | 文件访问 URL。 |
    | `file_type` | `str` | `""` | 文件类型。模型会统一转成大写。 |
    | `display_name` | `str` | `""` | 展示文件名。`upload_file()` 中默认使用本地文件名。 |
    | `file_size` | `int` | `0` | 文件大小，单位为 bytes。 |
    | `animated` | `bool` | `False` | 是否为动画图片或动态资源。 |

[//]: # (=== "内部流程")

[//]: # ()
[//]: # (    `upload_file&#40;&#41;` 内部流程如下：)

[//]: # ()
[//]: # (    1. 请求上传 ticket：)

[//]: # ()
[//]: # (        ```python)

[//]: # (        await self._request_data&#40;)

[//]: # (            "PUT",)

[//]: # (            "/rtc/v1/cos/v1/signedUploadUrl",)

[//]: # (            body={"type": file_type, "ext": ext},)

[//]: # (        &#41;)

[//]: # (        ```)

[//]: # ()
[//]: # (    2. 将接口返回解析为 `UploadTicket`。)

[//]: # ()
[//]: # (    3. 读取本地文件 bytes。)

[//]: # ()
[//]: # (    4. 使用 `PUT` 请求把文件 bytes 上传到 `ticket.signed_url`。)

[//]: # ()
[//]: # (    5. 如果上传响应状态码不是 `200` 或 `201`，抛出 `OopzApiError`。)

[//]: # ()
[//]: # (    6. 使用上传 ticket 和本地文件信息构造 `UploadedFileResult`。)

[//]: # ()
[//]: # (    上传 ticket 对应模型：`oopz_sdk.models.UploadTicket`)

[//]: # ()
[//]: # (    | 字段 | 类型 | 默认值 | 说明 |)

[//]: # (    | --- | --- | --- | --- |)

[//]: # (    | `auth` | `str` | `""` | 上传认证信息。 |)

[//]: # (    | `expire_in_second` | `int` | `0` | 上传 ticket 过期时间，单位为秒。 |)

[//]: # (    | `file_key` | `str` | `""` | 上传后得到的文件 key。 |)

[//]: # (    | `signed_url` | `str` | `""` | 用于 PUT 上传文件的签名 URL。 |)

[//]: # (    | `url` | `str` | `""` | 上传后文件的访问 URL。 |)

=== "异常"

    可能抛出的异常：

    | 场景 | 异常 |
    | --- | --- |
    | 上传 ticket 响应格式不是字典 | `OopzApiError` |
    | 上传 ticket 缺少 `file`、`signedUrl` 或 `url` | `OopzApiError` |
    | 本地文件不存在或无法读取 | `FileNotFoundError` / `OSError` |
    | 文件 PUT 上传失败 | `OopzApiError` |

---

## 与消息发送配合

如果你只是想发送图片，通常不需要手动调用 `upload_file()`。

推荐使用 `Image` 配合 `send_message()`，SDK 会在发送前自动上传本地图片。

```python
from oopz_sdk.models.segment import Image

await bot.messages.send_message(
    Image("./demo.png"),
    area=area,
    channel=channel,
)
```

=== "自动上传流程"

    当 `send_message()` 接收到本地图片 Segment 时，SDK 会自动：

    1. 读取图片宽高和文件大小。
    2. 调用 `bot.media.upload_file(...)` 上传图片。
    3. 根据上传结果创建新的 `Image` Segment。
    4. 生成 Oopz 图片占位文本：

        ```text
        ![IMAGEw{width}h{height}]({file_key})
        ```

    5. 生成图片附件信息。
    6. 发送最终消息。

=== "Image Segment 字段"

    对应模型：`oopz_sdk.models.segment.Image`

    | 字段 / 属性 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `file_path` | `str` | `""` | 本地文件路径。 |
    | `local_path` | `str` | `""` | 本地文件路径的另一种传入方式。 |
    | `file_key` | `str` | `""` | 已上传文件 key。 |
    | `url` | `str` | `""` | 已上传文件 URL。 |
    | `width` | `int` | `0` | 图片宽度。 |
    | `height` | `int` | `0` | 图片高度。 |
    | `file_size` | `int` | `0` | 文件大小，单位为 bytes。 |
    | `hash` | `str` | `""` | 文件 hash。 |
    | `animated` | `bool` | `False` | 是否为动画图片。 |
    | `display_name` | `str` | `""` | 展示文件名。 |
    | `preview_file_key` | `str` | `""` | 预览文件 key。 |
    | `is_uploaded` | `bool` | - | 是否已经有 `file_key` 和 `url`。 |
    | `has_local_file` | `bool` | - | 是否有本地文件路径。 |
    | `source_path` | `str` | - | 实际使用的本地路径，优先 `file_path`，其次 `local_path`。 |
    | `can_send` | `bool` | - | 是否可以发送；已上传或有本地文件时为 `True`。 |

=== "手动上传后复用"

    如果你希望先上传图片，再多次复用上传结果，可以手动调用 `upload_file()`，再创建 `Image.from_uploaded()`。

    ```python
    from oopz_sdk.models.segment import Image

    uploaded = await bot.media.upload_file(
        file="./demo.png",
        file_type="IMAGE",
        ext="png",
    )

    image = Image.from_uploaded(
        file_key=uploaded.file_key,
        url=uploaded.url,
        width=640,
        height=360,
        file_size=uploaded.file_size,
        animated=uploaded.animated,
        display_name=uploaded.display_name,
    )

    await bot.messages.send_message(
        image,
        area=area,
        channel=channel,
    )
    ```
---

## 与附件模型的关系

`upload_file()` 返回的是 `UploadedFileResult`，它表示“上传结果”。

真正发送图片消息时，SDK 会进一步把图片 Segment 转换成 `ImageAttachment`。

```python
attachment = image.to_attachment()
```

=== "ImageAttachment 字段"

    对应模型：`oopz_sdk.models.ImageAttachment`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `file_key` | `str` | `""` | 文件 key。 |
    | `url` | `str` | `""` | 文件 URL。 |
    | `attachment_type` | `str` | `""` | 附件类型。图片附件为 `IMAGE`。 |
    | `display_name` | `str` | `""` | 展示文件名。 |
    | `file_size` | `int` | `0` | 文件大小，单位为 bytes。 |
    | `animated` | `bool` | `False` | 是否为动画图片。 |
    | `hash` | `str` | `""` | 文件 hash。 |
    | `width` | `int` | `0` | 图片宽度。 |
    | `height` | `int` | `0` | 图片高度。 |
    | `preview_file_key` | `str` | `""` | 预览文件 key。 |

=== "注意事项"

    目前 `Attachment.parse()` 只支持解析 `IMAGE` 类型附件。

    如果接口返回其他 `attachment_type`，例如 `AUDIO`、`FILE` 或未知类型，当前模型不会自动解析为具体附件模型。