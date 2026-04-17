"""最小发送消息示例。"""

from oopz_sdk import MessageSendResult, OopzConfig, OopzRESTClient


def main() -> None:
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
        default_area="默认域ID",
        default_channel="默认频道ID",
    )

with OopzRESTClient(config) as sender:
        result: MessageSendResult = sender.send_message("Hello Oopz!")
        print(f"发送成功，message_id={result.message_id or 'unknown'}")


if __name__ == "__main__":
    main()
