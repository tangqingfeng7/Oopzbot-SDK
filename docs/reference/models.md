# 数据模型

SDK 使用 `pydantic v2` 对响应和事件进行建模。常见模型位于 `oopz_sdk.models`。

## 消息相关

| 模型 | 说明 |
| --- | --- |
| `Message` | Oopz 消息模型，包含 `area`、`channel`、`message_id`、`sender_id`、`content`、`attachments` 等。 |
| `MessageSendResult` | 发送消息结果，通常包含 `message_id`。 |
| `PrivateSession` | 私信会话。 |
| `Attachment` | 附件基类。 |
| `ImageAttachment` | 图片附件。 |
| `UploadedFileResult` | 上传文件结果。 |
| `OperationResult` | 通用操作结果。 |

## Segment 模型

| 类型 | 说明 |
| --- | --- |
| `Text` | 文本片段。 |
| `Mention` | 艾特指定用户。 |
| `MentionAll` | 艾特全体。 |
| `Image` | 图片片段，支持本地文件或已上传图片。 |

## 域与频道

| 模型 | 说明 |
| --- | --- |
| `JoinedAreaInfo` | 当前用户加入的域信息。 |
| `AreaInfo` | 域详细信息。 |
| `AreaMembersPage` | 域成员分页。 |
| `AreaUserDetail` | 用户在域内的详情、身份组与禁用状态。 |
| `RoleInfo` | 身份组信息。 |
| `ChannelGroupInfo` | 频道分组。 |
| `ChannelSetting` | 频道设置。 |
| `ChannelEdit` | 频道编辑请求模型。 |
| `CreateChannelResult` | 创建频道结果。 |
| `ChannelSign` | 进入频道或语音频道时返回的 sign 信息。 |
| `VoiceChannelMembersResult` | 语音频道成员集合。 |

## 用户与关系

| 模型 | 说明 |
| --- | --- |
| `UserInfo` | 用户基本信息。 |
| `Profile` | 用户完整资料。 |
| `UserLevelInfo` | 用户等级信息。 |
| `Friendship` | 好友关系。 |
| `FriendshipRequest` | 好友请求。 |

## 模型使用建议

- 优先使用模型字段，不要直接依赖原始 payload。
- 如果 API 变更导致字段缺失或类型变化，模型会尽量规范化；严重格式错误会抛出 `OopzApiError`。
- 调试时可以使用 `model.model_dump(by_alias=True)` 查看接近 API 格式的数据。
