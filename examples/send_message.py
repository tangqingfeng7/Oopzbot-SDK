"""最小发送消息示例。"""

from oopz import OopzConfig, OopzSender


def main() -> None:
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
        default_area="默认域ID",
        default_channel="默认频道ID",
    )

    with OopzSender(config) as sender:
        sender.send_message("Hello Oopz!")


if __name__ == "__main__":
    main()
