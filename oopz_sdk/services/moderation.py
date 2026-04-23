from __future__ import annotations

import logging
from oopz_sdk import models

from . import BaseService
from ..models import TextMuteInterval, VoiceMuteInterval

logger = logging.getLogger("oopz_sdk.services.moderation")


class Moderation(BaseService):
    """Moderation-related platform capabilities."""

    async def mute_user(
        self,
        area: str,
        uid: str,
        duration: TextMuteInterval | int | None = TextMuteInterval.M5,
    ) -> models.OperationResult:
        """Mute a user's text permission in an area."""
        if uid.strip() == "":
            raise ValueError("uid is required for mute_user")
        if area.strip() == "":
            raise ValueError("area is required for mute_user")

        # 判断并给默认值
        if duration is None:
            duration = TextMuteInterval.M5
        if isinstance(duration, TextMuteInterval):
            interval_id = str(duration.interval_id)
        else:
            interval_id = str(TextMuteInterval.pick(int(duration)).interval_id)

        data = await self._request_data(
            "PATCH",
            "/client/v1/area/v1/member/v1/disableText",
            params={"area": area, "target": uid, "intervalId": interval_id}
        )
        return models.OperationResult.from_api(data)

    async def unmute_user(self, area: str, uid: str) -> models.OperationResult:
        """Recover a user's text permission in an area."""
        if uid.strip() == "":
            raise ValueError("uid is required for unmute_user")
        if area.strip() == "":
            raise ValueError("area is required for unmute_user")

        data = await self._request_data(
            "PATCH",
            "/client/v1/area/v1/member/v1/recoverText",
            params={"area": area, "target": uid}
        )
        return models.OperationResult.from_api(data)

    async def mute_mic(
        self,
        uid: str,
        area: str,
        duration: VoiceMuteInterval | int | None = VoiceMuteInterval.M5,
    ) -> models.OperationResult:
        """Mute a user's voice permission in an area."""
        if uid.strip() == "":
            raise ValueError("uid is required for mute_mic")
        if area.strip() == "":
            raise ValueError("area is required for mute_mic")

        if duration is None:
            duration = VoiceMuteInterval.M5
        if isinstance(duration, VoiceMuteInterval):
            interval_id = str(duration.interval_id)
        else:
            interval_id = str(VoiceMuteInterval.pick(int(duration)).interval_id)

        params = {"area": area, "target": uid, "intervalId": interval_id}
        data = await self._request_data(
            "PATCH",
            "/client/v1/area/v1/member/v1/disableVoice",
            params=params,
            body=params,
        )
        return models.OperationResult.from_api(data)

    async def unmute_mic(self, area: str, uid: str) -> models.OperationResult:
        """Recover a user's voice permission in an area."""
        if uid.strip() == "":
            raise ValueError("uid is required for unmute_mic")
        if area.strip() == "":
            raise ValueError("area is required for unmute_mic")

        data = await self._request_data(
            "PATCH",
            "/client/v1/area/v1/member/v1/recoverVoice",
            params={"area": area, "target": uid}
        )
        return models.OperationResult.from_api(data)

    async def remove_from_area(self, area: str, uid: str) -> models.OperationResult:
        """Remove a user from an area."""
        if uid.strip() == "":
            raise ValueError("uid is required for unmute_mic")
        if area.strip() == "":
            raise ValueError("area is required for unmute_mic")

        data = await self._request_data(
            "POST",
            "/area/v3/remove",
            body={"area": area, "target": uid}
        )
        return models.OperationResult.from_api(data)

    async def block_user_in_area(self, area: str, uid: str) -> models.OperationResult:
        """Block a user in an area."""
        if uid.strip() == "":
            raise ValueError("uid is required for block_user_in_area")
        if area.strip() == "":
            raise ValueError("area is required for block_user_in_area")

        params = {"area": area, "target": uid}
        data = await self._request_data(
            "DELETE",
            "/client/v1/area/v1/block",
            params=params,
        )
        return models.OperationResult.from_api(data)

    async def get_area_blocks(
        self,
        area: str,
        name: str = ""
    ) -> list[models.UserInfo]:
        """Get the block list for an area."""
        if area.strip() == "":
            raise ValueError("area is required for get_area_blocks")
        data = await self._request_data(
            "GET",
            "/client/v1/area/v1/areaSettings/v1/blocks",
            params={"area": area, "name": name},
        )

        return [models.UserInfo.from_api(d) for d in data]


    async def unblock_user_in_area(self, area: str, uid: str) -> models.OperationResult:
        """Unblock a user in an area."""
        if area.strip() == "":
            raise ValueError("area is required for unblock_user_in_area")
        if uid.strip() == "":
            raise ValueError("uid is required for unblock_user_in_area")
        params = {"area": area, "target": uid}
        data = await self._request_data(
            "PATCH",
            "/client/v1/area/v1/unblock",
            params=params
        )
        return models.OperationResult.from_api(data)
