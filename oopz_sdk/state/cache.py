from typing import Optional

from . import TTLCache
from .. import models


class CacheStore:
    def __init__(self, config):
        self.identity: Optional[models.Profile] = None
        self.persons = TTLCache(
            max_entries=getattr(config, "person_cache_max_entries", 5000),
            ttl=getattr(config, "person_cache_ttl", 1800.0),
        )

        self.areas = TTLCache(
            max_entries=getattr(config, "area_cache_max_entries", 1000),
            ttl=getattr(config, "area_cache_ttl", 1800.0),
        )

        self.area_channels = TTLCache(
            max_entries=getattr(config, "area_channels_cache_max_entries", 1000),
            ttl=getattr(config, "area_channels_cache_ttl", 1800.0),
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

    def get_identity(self):
        return self.identity

    def set_identity(self, identity):
        self.identity = identity

    def invalidate_identity(self):
        self.identity = None

    def get_person(self, uid: str):
        return self.persons.get(uid)

    def set_person(self, uid: str, person):
        self.persons.set(uid, person)

    def get_area_user(self, area: str, uid: str):
        return self.area_users.get((area, uid))

    def set_area_user(self, area: str, uid: str, user):
        self.area_users.set((area, uid), user)

    def get_area(self, area: str):
        return self.areas.get(area)

    def set_area(self, area: str, info):
        self.areas.set(area, info)

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

    def invalidate_area_user(self, area: str, uid: str):
        self.area_users.delete((area, uid))

    def invalidate_area_members_page(
        self,
        area: str,
        offset_start: int,
        offset_end: int,
    ):
        self.area_members_pages.delete((area, offset_start, offset_end))

    def invalidate_area_members_pages(self):
        self.area_members_pages.clear()

    def invalidate_area(self, area: str):
        self.areas.delete(area)
        self.area_channels.delete(area)

        # 注意：这里没法高效删除所有 (area, start, end)
        # 因为当前 TTLCache 没有 delete_by_prefix。
        # 第一版可以直接清空所有成员分页缓存。
        self.area_members_pages.clear()