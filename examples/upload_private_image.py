"""上传图片并通过私信发送示例。"""

import asyncio

from oopz_sdk import OopzConfig, OopzRESTClient


async def main() -> None:
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    )

    async with OopzRESTClient(config) as sender:
        result = await sender.upload_and_send_private_image(
            target="目标UID",
            file_path="demo.png",
            text="这是一张通过 SDK 上传的图片",
        )
        print(f"私信发送成功，频道={result.channel}，message_id={result.message_id or 'unknown'}")


if __name__ == "__main__":
    asyncio.run(main())
