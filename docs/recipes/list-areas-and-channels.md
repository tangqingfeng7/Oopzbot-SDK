# 列出 area 和 channel

很多接口都需要 `area` 和 `channel`。这个示例会列出当前账号已加入的域和每个域下的频道。

```python
import asyncio
import os

from oopz_sdk import OopzConfig, OopzRESTClient


async def main() -> None:
    config = OopzConfig(
        device_id=os.environ["OOPZ_DEVICE_ID"],
        person_uid=os.environ["OOPZ_PERSON_UID"],
        jwt_token=os.environ["OOPZ_JWT_TOKEN"],
        private_key=os.environ["OOPZ_PRIVATE_KEY"],
    )

    async with OopzRESTClient(config) as client:
        areas = await client.areas.get_joined_areas()

        for area in areas:
            print(f"[AREA] {area.name}  id={area.area_id}")

            groups = await client.areas.get_area_channels(area.area_id)
            for group in groups:
                print(f"  [GROUP] {group.name}  id={group.group_id}")
                for channel in group.channels:
                    print(f"    [CHANNEL] {channel.name}  id={channel.channel_id}  type={channel.channel_type}")


asyncio.run(main())
```

如果你是在事件 handler 里需要当前消息的 `area` 和 `channel`，可以直接从消息对象里取：

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig
from oopz_sdk.events import EventContext
from oopz_sdk.models import Message

bot = OopzBot(OopzConfig(
    device_id="你的设备 ID",
    person_uid="机器人账号 UID",
    jwt_token="登录态 JWT",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
))


@bot.on_message
async def handle_message(message: Message, ctx: EventContext):
    print("area:", message.area)
    print("channel:", message.channel)



async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```
