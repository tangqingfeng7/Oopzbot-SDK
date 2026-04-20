"""最小发送消息示例。"""

import asyncio

from oopz_sdk import MessageSendResult, OopzConfig, OopzRESTClient


async def main() -> None:
    area_id = "你的域ID"
    channel_id = "你的频道ID"
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    )

    async with OopzRESTClient(config) as sender:
        result: MessageSendResult = await sender.send_message(
            "Hello Oopz!",
            area=area_id,
            channel=channel_id,
        )
        print(f"发送成功，message_id={result.message_id or 'unknown'}")


if __name__ == "__main__":
    asyncio.run(main())
