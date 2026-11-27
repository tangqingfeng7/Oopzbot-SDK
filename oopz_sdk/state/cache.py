from typing import Optional

from . import TTLCache
from .. import models


class CacheStore:
    def __init__(self, config):
        self._identity: Optional[models.Profile] = None
        self._userinfo = TTLCache(
            max_entries=getattr(config, "userinfo_cache_max_entries", 5000),
            ttl=getattr(config, "userinfo_cache_ttl", 1800.0),
        )

        self._area_channels = TTLCache(
            max_entries=getattr(config, "area_channels_cache_max_entries", 1000),
            ttl=getattr(config, "area_channels_cache_ttl", 1800.0),
        )

        self._person_profiles = TTLCache(
            max_entries=getattr(config, "person_profiles_cache_max_entries", 3000),
            ttl=getattr(config, "person_profile_cache_ttl", 1800.0),
        )

        self._area_user_nicknames = TTLCache(
            max_entries=getattr(config, "area_user_nickname_cache_max_entries", 20000),
            ttl=getattr(config, "area_user_nickname_cache_ttl", 300.0),
        )

        # 分页成员缓存，短 TTL，只用于防止短时间重复请求
        self._area_members_pages = TTLCache(
            max_entries=getattr(config, "area_members_page_cache_max_entries", 200),
            ttl=getattr(
                config,
                "area_members_page_cache_ttl",
                10.0,
            ),
        )

    # identity
    def get_identity(self) -> models.Profile | None:
        return self._identity

    def set_identity(self, identity: models.Profile) -> None:
        self._identity = identity

    def invalidate_identity(self) -> None:
        self._identity = None

    # userinfo
    def get_userinfo(self, uid: str) -> models.UserInfo | None:
        return self._userinfo.get(uid)

    def set_userinfo(self, uid: str, user: models.UserInfo) -> None:
        self._userinfo.set(uid, user)

    def invalidate_userinfo(self, uid: str) -> None:
        self._userinfo.delete(uid)

    def invalidate_userinfos(self) -> None:
        self._userinfo.clear()

    # person profile
    def get_person_profile(self, uid: str) -> models.Profile | None:
        return self._person_profiles.get(uid)

    def set_person_profile(self, uid: str, profile: models.Profile) -> None:
        self._person_profiles.set(uid, profile)

    def invalidate_person_profile(self, uid: str) -> None:
        self._person_profiles.delete(uid)

    def invalidate_person_profiles(self) -> None:
        self._person_profiles.clear()

    # area channels
    def get_area_channels(self, area: str) -> list[models.ChannelGroupInfo] | None:
        return self._area_channels.get(area)

    def set_area_channels(
        self,
        area: str,
        channels: list[models.ChannelGroupInfo],
    ) -> None:
        self._area_channels.set(area, channels)

    def invalidate_area_channels(self, area: str) -> None:
        self._area_channels.delete(area)

    def invalidate_all_area_channels(self) -> None:
        self._area_channels.clear()

    # area members page
    def get_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
    ) -> models.AreaMembersPage | None:
        return self._area_members_pages.get((area, offset_start, offset_end))

    def set_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
        page: models.AreaMembersPage,
    ) -> None:
        self._area_members_pages.set((area, offset_start, offset_end), page)

    def invalidate_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
    ) -> None:
        self._area_members_pages.delete((area, offset_start, offset_end))

    def invalidate_area_members_pages(self, area: str | None = None) -> None:
        if area is None:
            self._area_members_pages.clear()
            return

        self._area_members_pages.delete_where(
            lambda key: isinstance(key, tuple)
            and len(key) >= 1
            and key[0] == area
        )

    def invalidate_area_members_pages_for_user(self, uid: str) -> None:
        self._area_members_pages.delete_values_where(
            lambda page: any(member.uid == uid for member in page.members)
        )

    # area user nicknames
    def get_area_user_nickname(self, area: str, uid: str) -> str | None:
        return self._area_user_nicknames.get((area, uid))

    def set_area_user_nickname(self, area: str, uid: str, nickname: str) -> None:
        self._area_user_nicknames.set((area, uid), nickname)

    def invalidate_area_user_nickname(self, area: str, uid: str) -> None:
        self._area_user_nicknames.delete((area, uid))

    def invalidate_area_user_nicknames(self, area: str | None = None) -> None:
        if area is None:
            self._area_user_nicknames.clear()
            return

        self._area_user_nicknames.delete_where(
            lambda key: isinstance(key, tuple)
            and len(key) >= 1
            and key[0] == area
        )
