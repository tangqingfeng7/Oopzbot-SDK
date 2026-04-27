# Moderation Service

入口：`client.moderation` 或 `bot.moderation`。

## 方法列表

| 方法 | 说明 | 返回 |
| --- | --- | --- |
| `mute_user(area, uid, ...)` | 域内禁言用户。 | `OperationResult` |
| `unmute_user(area, uid)` | 解除禁言。 | `OperationResult` |
| `mute_mic(area, uid, ...)` | 域内禁麦用户。 | `OperationResult` |
| `unmute_mic(area, uid)` | 解除禁麦。 | `OperationResult` |
| `remove_from_area(area, uid)` | 将用户移出域。 | `OperationResult` |
| `block_user_in_area(area, uid)` | 拉黑域内用户。 | `OperationResult` |
| `get_area_blocks(area, name="")` | 获取域黑名单，可按名称过滤。 | `list[UserInfo]` |
| `unblock_user_in_area(area, uid)` | 取消拉黑。 | `OperationResult` |

## 禁言与解禁

```python
await bot.moderation.mute_user(area="域 ID", uid="用户 UID")
await bot.moderation.unmute_user(area="域 ID", uid="用户 UID")
```

## 禁麦与解除禁麦

```python
await bot.moderation.mute_mic(area="域 ID", uid="用户 UID")
await bot.moderation.unmute_mic(area="域 ID", uid="用户 UID")
```

## 踢出与拉黑

```python
await bot.moderation.remove_from_area(area="域 ID", uid="用户 UID")
await bot.moderation.block_user_in_area(area="域 ID", uid="用户 UID")
```

管理类接口通常需要机器人账号在目标域内具备相应权限。
