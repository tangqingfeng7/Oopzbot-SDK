# 数据模型

SDK 使用 `pydantic v2` 对响应和事件进行建模。常用入口模型通常从 `oopz_sdk.models` 导出；少数嵌套模型只在具体子模块中导出，下表会标出可直接导入的路径。

> 除 Segment 分段类型外，响应、事件和附件等 Pydantic 模型都继承自内部 `BaseModel`（`extra="ignore"` + `populate_by_name=True`），调用 `model.model_dump(by_alias=True)` 可以拿到接近 API 的 camelCase 数据。

## 消息相关

| 模型                  | 导入路径 | 说明                                                                                                                            |
|---------------------|---|-------------------------------------------------------------------------------------------------------------------------------|
| `Message`           | `oopz_sdk.models.Message` | Oopz 消息模型。常用字段：`area`、`channel`、`message_id`、`sender_id`（=`person`）、`text`、`content`、`attachments`、`mention_list`、`is_mention_all`、`reference_message_id`、`timestamp`。详见 [Message 字段](#message-字段)。 |
| `MentionInfo`       | `oopz_sdk.models.message.MentionInfo` | 单条消息里的一个 mention，字段：`person`、`is_bot`、`bot_type`、`offset`。 |
| `MediaInfo`         | `oopz_sdk.models.message.MediaInfo` | 消息附带的视频/封面元信息（`previewImage` / `rawVideo`）。字段：`file_key`、`file_size`、`hash`、`url`、`width`、`height`。 |
| `MessageSendResult` | `oopz_sdk.models.MessageSendResult` | 发送消息成功的返回值，含 `message_id` 和 `timestamp`。 |
| `PrivateSession`    | `oopz_sdk.models.PrivateSession` | 私信会话。字段：`uid`、`session_id`、`last_time`、`mute`。 |
| `Attachment`        | `oopz_sdk.models.Attachment` | 附件抽象基类。子类：`ImageAttachment` / `AudioAttachment` / `FileAttachment`。`Attachment.parse(payload)` 会按 `attachmentType` 自动派发到正确子类。 |
| `ImageAttachment`   | `oopz_sdk.models.ImageAttachment` | 图片附件，含 `width` / `height` / `preview_file_key` / `animated`。可用 `ImageAttachment.from_manually(...)` 手动构造。 |
| `AudioAttachment`   | `oopz_sdk.models.AudioAttachment` | 语音附件（`attachmentType=AUDIO`），额外字段 `duration`。 |
| `FileAttachment`    | `oopz_sdk.models.FileAttachment` | 普通文件附件（`attachmentType=FILE`）。 |
| `UploadTicket`      | `oopz_sdk.models.UploadTicket` | 上传服务返回的临时凭证：`auth`、`signed_url`、`url`、`file_key`、`expire_in_second`。 |
| `UploadedFileResult`| `oopz_sdk.models.UploadedFileResult` | 上传完成后的结果：`file_key`、`url`、`file_type`、`display_name`、`file_size`、`animated`。 |

### Message 字段

| 字段                     | 类型                  | API 别名               | 说明                            |
|------------------------|---------------------|----------------------|-------------------------------|
| `target`               | `str`               | `target`             | 私信目标 UID；频道消息为空。              |
| `area`                 | `str`               | `area`               | 域 ID。私信为空字符串。                 |
| `channel`              | `str`               | `channel`            | 频道 ID 或私信会话 ID。               |
| `message_type`         | `str`               | `type`               | 消息类型，例如 `TEXT`。               |
| `message_id`           | `str`               | `messageId`          | 消息 ID。                        |
| `client_message_id`    | `str`               | `clientMessageId`    | 客户端生成的消息 ID。                  |
| `timestamp`            | `str`               | `timestamp`          | 微秒级时间戳。                       |
| `sender_id`            | `str`               | `person`             | 发送者 UID。                      |
| `content`              | `str`               | `content`            | 消息原始 content（含 markdown / 占位符）。 |
| `text`                 | `str`               | `text`               | 渲染用的纯文本。                      |
| `edit_time`            | `int`               | `editTime`           | 编辑时间，未编辑为 `0`。                |
| `top_time`             | `str`               | `topTime`            | 置顶时间。缺失、`None` 或数值 `0` 会归一为空字符串；服务端下发字符串 `"0"` 时会原样保留。 |
| `is_mention_all`       | `bool`              | `isMentionAll`       | 是否艾特全体。                       |
| `mention_list`         | `list[MentionInfo]` | `mentionList`        | mention 列表。                   |
| `style_tags`           | `list[Any]`         | `styleTags`          | 样式标签，例如 `IMPORTANT`。          |
| `area_page`            | `str`               | `areaPage`           | 域翻页/分页相关字段，多数消息为空。     |
| `area_count`           | `int`               | `areaCount`          | 域内某种计数，缺失时为 `0`。          |
| `sender_is_bot`        | `bool`              | `senderIsBot`        | 发送者是否为机器人。                    |
| `sender_bot_type`      | `str`               | `senderBotType`      | 机器人类型。                        |
| `attachments`          | `list[Attachment]`  | `attachments`        | 解析后的附件列表。                     |
| `reference_message`    | `Any`               | `referenceMessage`   | 被回复消息。                        |
| `reference_message_id` | `str`               | `referenceMessageId` | 被回复消息 ID。                     |
| `preview_image`        | `MediaInfo \| None`  | `previewImage`       | 视频消息的预览图。                     |
| `raw_video`            | `MediaInfo \| None`  | `rawVideo`           | 视频消息的原始流信息。                   |
| `cards`                | `Any`               | `cards`              | 卡片消息原始数据，未建模。                 |
| `display_name`         | `str`               | `displayName`        | 展示名。                          |
| `duration`             | `int`               | `duration`           | 媒体时长（秒）。                      |

`Message` 还提供两个 cached property：

- `message.segments` —— 把 `text` / `attachments` / `mention_list` 解析成 `Segment` 列表，方便结构化处理。
- `message.plain_text` —— 把所有 `Text` segment 拼起来的纯文本。

## Segment 模型

`oopz_sdk.models.segment` 下提供消息分段类型，构造发送内容时使用。

| 类型           | 说明                          |
|--------------|-----------------------------|
| `Text`       | 文本片段。                       |
| `Mention`    | 艾特指定用户，构造参数为 `user_id`。     |
| `MentionAll` | 艾特全体。                       |
| `Image`      | 图片片段，可用 `Image(...)` / `Image.from_file(...)` 从图片输入构造；输入类型与 [Media Service](media-service.md) 的 `ImageInput` 一致，支持路径、bytes、base64 / data URL 和 file-like。也可用 `Image.from_uploaded(...)` / `Image.from_attachment(...)` 从已上传结果构造。 |

`build_segments(segments)` 把已 resolve 的 segment 列表编译成 Oopz `send_message` 所需的 `(text, attachments)`。

Segment 分段类型不是 Pydantic 模型，不提供 `model_dump()` 或 `to_dict()`。需要查看单个片段的发送文本时使用 `segment.to_message_text()`；需要编译为 `send_message()` 使用的 `(text, attachments)` 时使用 `build_segments(...)`。

## 域与频道

| 模型                          | 导入路径 | 说明                                                                |
|-----------------------------|---|-------------------------------------------------------------------|
| `JoinedAreaInfo`            | `oopz_sdk.models.JoinedAreaInfo` | 当前用户加入的域信息（`area_id`、`code`、`name`、`avatar`、`level` 等）。 |
| `AreaInfo`                  | `oopz_sdk.models.AreaInfo` | 域详细信息，含 `role_list`、`area_role_infos`、`subscribed` 等。 |
| `AreaRole`                  | `oopz_sdk.models.area.AreaRole` | 域内单个身份组（`role_id`、`name`、`type`、`sort` 等）。 |
| `AreaRoleInfo`              | `oopz_sdk.models.area.AreaRoleInfo` | 当前用户在域内的角色与权限（`is_owner`、`max_role`、`roles`、`privilege_keys`）。 |
| `AreaMemberInfo`            | `oopz_sdk.models.area.AreaMemberInfo` | 域成员摘要（`uid`、`role`、`online`、`role_status` 等）。 |
| `AreaRoleCountInfo`         | `oopz_sdk.models.area.AreaRoleCountInfo` | 域内身份组人数统计。 |
| `AreaMembersPage`           | `oopz_sdk.models.AreaMembersPage` | 域成员分页结果（`total_count`、`members`、`role_count`、`from_cache`）。 |
| `AreaUserDetail`            | `oopz_sdk.models.AreaUserDetail` | 用户在指定域内的详情、身份组与禁用状态。 |
| `RoleInfo`                  | `oopz_sdk.models.RoleInfo` | 用户身份组列表项，含 `owned` 字段标识当前用户是否拥有该身份组。 |
| `ChannelGroupInfo`          | `oopz_sdk.models.ChannelGroupInfo` | 频道分组（包含其下 `channels` 列表）。 |
| `ChannelInfo`               | `oopz_sdk.models.area.ChannelInfo` | 频道分组里的单个频道项。 |
| `ChannelSettings`           | `oopz_sdk.models.area.ChannelSettings` | 频道分组场景下使用的频道设置。 |
| `ChannelSetting`            | `oopz_sdk.models.ChannelSetting` | `Channel.get_channel_setting_info(channel)` 返回的频道设置。 |
| `ChannelEdit`               | `oopz_sdk.models.ChannelEdit` | 频道编辑请求模型。SDK 内部用 `ChannelEdit.from_setting(setting, area=..., channel=...)` 在 `update_channel(...)` 里构造请求 body，正常情况下不需要直接调用。 |
| `ChannelType`               | `oopz_sdk.models.ChannelType` | 枚举：`TEXT` / `VOICE` / `AUDIO`（`AUDIO` 是历史协议中语音类型的别名，与 `VOICE` 等价）。 |
| `CreateChannelResult`       | `oopz_sdk.models.CreateChannelResult` | 创建频道结果，含新频道 ID 和默认设置。 |
| `ChannelSign`               | `oopz_sdk.models.ChannelSign` | 进入频道或语音频道时返回的 sign 信息（`agora_sign`、`room_id` 等）。 |
| `VoiceChannelMemberInfo`    | `oopz_sdk.models.channel.VoiceChannelMemberInfo` | 单个语音频道成员信息。 |
| `VoiceChannelMembersResult` | `oopz_sdk.models.VoiceChannelMembersResult` | 语音频道成员集合，按 `channel_id` 索引到成员列表。 |

## 用户与关系

| 模型                  | 说明                                                |
|---------------------|---------------------------------------------------|
| `UserInfo`          | 用户基本信息（公开资料）。                                     |
| `Profile`           | 用户完整资料，包含设置与隐私选项。                                 |
| `UserLevelInfo`     | 用户等级信息。                                           |
| `Friendship`        | 好友关系，字段：`uid`、`name`、`online`。                                       |
| `FriendshipRequest` | 好友请求记录。                                           |

## 通用

| 模型                  | 说明                                                                    |
|---------------------|-----------------------------------------------------------------------|
| `OperationResult`   | 通用操作结果：`ok: bool`、`message: str`。`OperationResult.from_api(...)` 会把 bool / dict 都规范化为该结构。 |

## 枚举

| 枚举                  | 说明                                              |
|---------------------|-------------------------------------------------|
| `ChannelType`       | 频道类型，`TEXT` / `VOICE` / `AUDIO`（`AUDIO` 是 `VOICE` 的旧别名）。     |
| `TextMuteInterval`  | `Moderation.mute_user(...)` 用的预设禁言时长（`S60` / `M5` / `H1` / `D1` / `D3` / `D7`，对应 60 秒、5 分钟、1 小时、1 / 3 / 7 天）。 |
| `VoiceMuteInterval` | `Moderation.mute_mic(...)` 用的预设禁麦时长（同上 `S60` / `M5` / `H1` / `D1` / `D3` / `D7`）。  |

## 模型使用建议

- 优先使用模型字段（多数为 snake_case 属性），不要直接依赖原始 payload。少数历史兼容字段例外，例如 `UserInfo.memberLevel` 当前仍保留 camelCase 属性名，没有 `member_level`。
- 如果 API 变更导致字段缺失或类型变化，模型会尽量规范化；严重格式错误会抛出 `OopzApiError`。
- 调试或回传给上游时使用 `model.model_dump(by_alias=True)` 拿到接近 API 的 camelCase 数据。
- 大多数模型的 `from_api(payload)` 会做严格校验；自己拼装时建议直接用 `Model(**kwargs)` 或 `Model.model_validate(payload)`。
