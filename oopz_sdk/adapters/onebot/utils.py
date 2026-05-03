from typing import Mapping, Any

from oopz_sdk import models


def model_to_userinfo_extra(
        model: models.UserInfo
) -> dict[str, Any]:
    return {
        "avatar": getattr(model, "avatar", ""),
        "avatar_frame": getattr(model, "avatar_frame", ""),
        "avatar_frame_animation": getattr(model, "avatar_frame_animation", ""),
        "avatar_frame_expire_time": getattr(model, "avatar_frame_expire_time", 0),

        "badges": getattr(model, "badges", None),
        "introduction": getattr(model, "introduction", ""),
        "mark": getattr(model, "mark", ""),
        "mark_expire_time": getattr(model, "mark_expire_time", 0),
        "mark_name": getattr(model, "mark_name", ""),

        "online": getattr(model, "online", False),

        "pid": getattr(model, "pid", ""),
        "status": getattr(model, "status", ""),
        "user_common_id": getattr(model, "user_common_id", ""),

        "member_level": getattr(model, "memberLevel", 0),
        "person_role": getattr(model, "person_role", ""),
        "person_type": getattr(model, "person_type", ""),
    }

def model_to_userinfo_dict(
    user_id: str,
    model: models.UserInfo,
    nickname_dict: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "user_id": getattr(model, "uid", "") or user_id,
        "user_name": getattr(model, "name", ""),
        "user_displayname": nickname_dict.get(user_id, ""),
        "extra": model_to_userinfo_extra(model),
    }


def model_to_profile_extra(profile: models.Profile) -> dict[str, Any]:
    return {
        "area_avatar": getattr(profile, "area_avatar", ""),
        "area_max_num": getattr(profile, "area_max_num", 0),
        "area_name": getattr(profile, "area_name", ""),

        "avatar": getattr(profile, "avatar", ""),
        "avatar_frame": getattr(profile, "avatar_frame", ""),
        "avatar_frame_animation": getattr(profile, "avatar_frame_animation", ""),
        "avatar_frame_expire_time": getattr(profile, "avatar_frame_expire_time", 0),

        "badges": getattr(profile, "badges", []),

        "banner": getattr(profile, "banner", ""),
        "card_decoration": getattr(profile, "card_decoration", ""),
        "card_decoration_expire_time": getattr(profile, "card_decoration_expire_time", 0),

        "community_personal_rec": getattr(profile, "community_personal_rec", False),
        "default_avatar": getattr(profile, "default_avatar", False),
        "default_name": getattr(profile, "default_name", False),

        "disabled_end_time": getattr(profile, "disabled_end_time", 0),
        "disabled_start_time": getattr(profile, "disabled_start_time", 0),

        "display_playing_state": getattr(profile, "display_playing_state", None),
        "display_type": getattr(profile, "display_type", ""),

        "fans_count": getattr(profile, "fans_count", 0),
        "fixed_private_message": getattr(profile, "fixed_private_message", False),
        "follow_count": getattr(profile, "follow_count", 0),
        "follow_private": getattr(profile, "follow_private", False),

        "greeting": getattr(profile, "greeting", ""),
        "introduction": getattr(profile, "introduction", ""),
        "ip_address": getattr(profile, "ip_address", ""),
        "is_abroad": getattr(profile, "is_abroad", False),

        "like_count": getattr(profile, "like_count", 0),

        "mark": getattr(profile, "mark", ""),
        "mark_expire_time": getattr(profile, "mark_expire_time", 0),
        "mark_name": getattr(profile, "mark_name", ""),

        "mobile_banner": getattr(profile, "mobile_banner", ""),
        "music_state": getattr(profile, "music_state", ""),
        "mute": getattr(profile, "mute", None),
        "mutual_follow_count": getattr(profile, "mutual_follow_count", 0),

        "name": getattr(profile, "name", ""),
        "online": getattr(profile, "online", False),

        "person_role": getattr(profile, "person_role", ""),
        "person_type": getattr(profile, "person_type", ""),
        "person_vip_end_time": getattr(profile, "person_vip_end_time", 0),
        "person_vip_start_time": getattr(profile, "person_vip_start_time", 0),

        "phone": getattr(profile, "phone", ""),
        "pid": getattr(profile, "pid", ""),
        "pid_level_name": getattr(profile, "pid_level_name", ""),
        "pid_tag_black": getattr(profile, "pid_tag_black", ""),
        "pid_tag_white": getattr(profile, "pid_tag_white", ""),

        "playing_game_image": getattr(profile, "playing_game_image", ""),
        "playing_state": getattr(profile, "playing_state", ""),
        "playing_time": getattr(profile, "playing_time", 0),

        "pwd_set_time": getattr(profile, "pwd_set_time", 0),
        "recommend_area": getattr(profile, "recommend_area", ""),
        "song_state": getattr(profile, "song_state", ""),

        "status": getattr(profile, "status", ""),
        "stealth": getattr(profile, "stealth", False),

        "uid": getattr(profile, "uid", ""),
        "use_booster": getattr(profile, "use_booster", False),
        "user_common_id": getattr(profile, "user_common_id", ""),
        "user_level": getattr(profile, "user_level", 0),

        "vip_id": getattr(profile, "vip_id", ""),
        "voice_disable": getattr(profile, "voice_disable", 0),

        "wx_nickname": getattr(profile, "wx_nickname", ""),
        "wx_union_id": getattr(profile, "wx_union_id", ""),
    }
