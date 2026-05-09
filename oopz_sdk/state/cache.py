from typing import Optional

from . import TTLCache
from .. import models


class CacheStore:
    def __init__(self, config):
        self.identity: Optional[models.Profile] = None
        self.userinfo = TTLCache(
            max_entries=getattr(config, "person_cache_max_entries", 5000),
            ttl=getattr(config, "person_cache_ttl", 1800.0),
        )

        self.area_channels = TTLCache(
            max_entries=getattr(config, "area_channels_cache_max_entries", 1000),
            ttl=getattr(config, "area_channels_cache_ttl", 1800.0),
        )

        self.person_profiles = TTLCache(
            max_entries=getattr(config, "person_profile_cache_max_entries", 3000),
            ttl=getattr(config, "person_profile_cache_ttl", 1800.0),
        )

        self.area_user_nicknames = TTLCache(
            max_entries=getattr(config, "area_user_nickname_cache_max_entries", 20000),
            ttl=getattr(config, "area_user_nickname_cache_ttl", 300.0),
        )

        # 分页成员缓存，短 TTL，只用于防止短时间重复请求
        self.area_members_pages = TTLCache(
            max_entries=getattr(config, "area_members_page_cache_max_entries", 200),
            ttl=getattr(
                config,
                "area_members_page_cache_ttl",
                getattr(config, "area_members_cache_ttl", 10.0),
            ),
        )

        self.user_profile = TTLCache()

    def get_identity(self) -> models.Profile:
        return self.identity

    def set_identity(self, identity: models.Profile):
        self.identity = identity

    def get_person_profile(self, uid: str) -> models.Profile:
        return self.person_profiles.get(uid)

    def set_person_profile(self, uid: str, profile):
        self.person_profiles.set(uid, profile)

    def invalidate_identity(self):
        self.identity = None

    def get_userinfo(self, uid: str) -> models.UserInfo:
        return self.userinfo.get(uid)

    def set_userinfo(self, uid: str, person: models.UserInfo):
        self.userinfo.set(uid, person)

    def get_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
    ):
        return self.area_members_pages.get((area, offset_start, offset_end))

    def set_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
        page,
    ):
        self.area_members_pages.set((area, offset_start, offset_end), page)


    def invalidate_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
    ):
        self.area_members_pages.delete((area, offset_start, offset_end))

    def invalidate_area_members_pages(self, area: str | None = None):
        if area is None:
            self.area_members_pages.clear()
            return

        self.area_members_pages.delete_where(
            lambda key: isinstance(key, tuple) and len(key) >= 1 and key[0] == area
        )

    def get_area_user_nickname(self, area: str, uid: str) -> str | None:
        return self.area_user_nicknames.get((area, uid))

    def set_area_user_nickname(self, area: str, uid: str, nickname: str) -> None:
        self.area_user_nicknames.set((area, uid), nickname)

    def invalidate_area_user_nickname(self, area: str, uid: str) -> None:
        self.area_user_nicknames.delete((area, uid))