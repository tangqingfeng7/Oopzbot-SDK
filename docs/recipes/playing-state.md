# 设置和读取当前动态

配置账号凭据后，可以直接用 REST 客户端设置动态。这个示例将当前账号的听歌动态设为「QQ音乐 · 七里香」，然后读回歌名。

```python
import asyncio

from oopz_sdk import OopzConfig, OopzRESTClient


async def main() -> None:
    config = await OopzConfig.from_env_async()
    async with OopzRESTClient(config) as client:
        result = await client.person.set_music_state("QQ音乐", "七里香")
        if not result.ok:
            raise RuntimeError(result.message or "设置听歌动态失败")
        state = await client.person.get_playing_state()
        print(state.music_state, state.song_state)


asyncio.run(main())
```

切换到游戏动态可调用 `set_game_state("组队中", game_id=116)`，结束展示时调用 `clear_playing_state()`。[当前动态接口](../reference/person-service.md#当前动态)
