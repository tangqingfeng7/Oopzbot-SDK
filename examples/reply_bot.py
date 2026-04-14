"""最小收消息并自动回复示例。"""

from oopz import ChatMessageEvent, OopzClient, OopzConfig, OopzSender


def main() -> None:
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
        default_area="默认域ID",
        default_channel="默认频道ID",
    )

    sender = OopzSender(config)

    def on_message(message: ChatMessageEvent) -> None:
        content = message.content
        if content.strip().lower() == "ping":
            sender.send_message(
                "pong",
                area=message.area,
                channel=message.channel,
            )

    client = OopzClient(config, on_chat_message=on_message)
    client.start()


if __name__ == "__main__":
    main()
