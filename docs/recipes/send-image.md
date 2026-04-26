# 发送图片

推荐使用 `Image.from_file()`。SDK 会自动读取图片尺寸、上传图片并构造消息内容。

```python
import asyncio
import os

from oopz_sdk import OopzConfig, OopzRESTClient
from oopz_sdk.models.segment import Text, Mention, Image


async def main() -> None:
    config = OopzConfig(
        device_id=os.environ["OOPZ_DEVICE_ID"],
        person_uid=os.environ["OOPZ_PERSON_UID"],
        jwt_token=os.environ["OOPZ_JWT_TOKEN"],
        private_key=os.environ["OOPZ_PRIVATE_KEY"],
    )

    async with OopzRESTClient(config) as client:
        await client.messages.send_message(
            Text("你好 "),
            Mention("2ce12124c07111ef9e5dc6b17c3481f1"),
            Text(" 这是一张图：\n"),
            Image.from_file("./demo.png"),
            area="域 ID",
            channel="频道 ID",
        )


asyncio.run(main())
```

如果图片路径不存在或图片格式无法识别，发送前会抛出异常。
