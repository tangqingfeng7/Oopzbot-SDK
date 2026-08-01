# General Service

`General Service` 用于获取不属于特定域、频道或用户的通用平台信息。

---

## `get_daily_speech()`

获取每日一言及其作者。

```python
speech = await client.general.get_daily_speech()

print(speech.words)
print(speech.author)
```

=== "参数"

    无参数。

=== "返回值"

    返回：`DailySpeech`。

    对应模型：`oopz_sdk.models.DailySpeech`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `words` | `str` | `""` | 每日一言的正文。 |
    | `author` | `str` | `""` | 作者或来源。 |

---
