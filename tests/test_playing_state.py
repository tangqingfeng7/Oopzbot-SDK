import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, call

from pydantic import ValidationError

from oopz_sdk import OopzBot, OopzRESTClient
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.models import AreaMembersPage, PlayingState, Profile
from oopz_sdk.testing.factories import make_config
from oopz_sdk.transport.http import HttpResponse


def response(payload: dict) -> HttpResponse:
    text = json.dumps(payload)
    return HttpResponse(status_code=200, headers={}, content=text.encode(), text=text)


class PlayingStateTest(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.client = OopzRESTClient(make_config())
        self.person = self.client.person
        self.request = AsyncMock(return_value=response({"status": True, "data": None}))
        self.client.transport.request = self.request

    async def test_game_music_and_clear_send_complete_state(self) -> None:
        self.assertTrue((await self.person.set_game_state("组队中", game_id=116)).ok)
        await self.person.set_game_state("原神")
        await self.person.set_music_state("QQ音乐", "七里香")
        await self.person.set_music_state("网易云音乐")
        await self.person.clear_playing_state()

        bodies = [
            {"display": "GAME", "playingState": "组队中", "musicState": "", "songState": "", "gameId": 116},
            {"display": "GAME", "playingState": "原神", "musicState": "", "songState": ""},
            {"display": "MUSIC", "playingState": "", "musicState": "QQ音乐", "songState": "七里香"},
            {"display": "MUSIC", "playingState": "", "musicState": "网易云音乐", "songState": ""},
            {"display": "", "playingState": "", "musicState": "", "songState": ""},
        ]
        self.assertEqual(self.request.await_args_list, [
            call("POST", "/person/v1/playingState/save", params=None, body=body) for body in bodies
        ])

    async def test_read_fetches_current_self_and_public_state(self) -> None:
        bot = OopzBot(make_config())
        bot.rest.transport.request = self.request
        bot.cache.set_identity(Profile.from_api({"displayType": "GAME", "playingState": "旧动态"}))
        bot.cache.set_person_profile("friend", Profile.from_api({"displayType": "MUSIC"}))
        self.request.side_effect = [
            response({"status": True, "data": {
                "displayType": "MUSIC", "musicState": "QQ音乐", "songState": "七里香",
                "displayPlayingState": "false",
            }}),
            response({"status": True, "data": {
                "displayType": "GAME", "playingState": "组队中", "playingGameImage": "icon.webp",
                "playingTime": 60,
            }}),
            response({"status": True, "data": {"displayType": None, "songState": None}}),
        ]

        mine = await bot.person.get_playing_state()
        friend = await bot.person.get_playing_state("friend")
        empty = await bot.person.get_playing_state(bot.config.person_uid)

        self.assertEqual(mine, PlayingState(
            display_type="MUSIC", music_state="QQ音乐", song_state="七里香", display_playing_state=False,
        ))
        self.assertEqual(friend, PlayingState(
            display_type="GAME", playing_state="组队中", playing_game_image="icon.webp", playing_time=60,
        ))
        self.assertEqual(empty, PlayingState())
        self.assertEqual(self.request.await_args_list, [
            call("GET", "/client/v1/person/v2/selfDetail", params={"uid": bot.config.person_uid}, body=None),
            call("GET", "/client/v1/person/v1/personDetail", params={"uid": "friend"}, body=None),
            call("GET", "/client/v1/person/v2/selfDetail", params={"uid": bot.config.person_uid}, body=None),
        ])

    async def test_malformed_activity_fields_raise_validation_error(self) -> None:
        self.request.return_value = response({"status": True, "data": {
            "playingState": {"name": "游戏"}, "playingTime": "invalid",
        }})
        with self.assertRaises(ValidationError) as error:
            await self.person.get_playing_state()
        self.assertEqual({item["loc"] for item in error.exception.errors()}, {("playingState",), ("playingTime",)})

    async def test_profile_caches_are_invalidated_only_after_success(self) -> None:
        uid = self.client.config.person_uid
        cached = Profile.from_api({"uid": uid, "displayType": "MUSIC", "songState": "七里香"})
        self.person.cache.set_identity(cached)
        self.person.cache.set_person_profile(uid, cached)
        self.person.cache.set_person_profile("friend", Profile.from_api({"uid": "friend"}))
        page = AreaMembersPage.from_api({"members": [{"uid": uid, "displayType": "MUSIC"}]})
        self.person.cache.set_area_members_page("area", 0, 20, page)
        other_page = AreaMembersPage.from_api({"members": [{"uid": "friend"}]})
        self.person.cache.set_area_members_page("area", 20, 40, other_page)
        self.request.side_effect = [
            response({"status": False, "message": "保存失败"}),
            response({"status": True, "data": False}),
            response({"status": True, "data": {"ok": False, "message": "未保存"}}),
            response({"status": True}),
            response({"status": True, "data": None}),
        ]

        with self.assertRaisesRegex(OopzApiError, "保存失败"):
            await self.person.clear_playing_state()
        self.assertFalse((await self.person.clear_playing_state()).ok)
        rejected = await self.person.clear_playing_state()
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.message, "未保存")
        with self.assertRaisesRegex(OopzApiError, "'data'"):
            await self.person.clear_playing_state()
        self.assertEqual(self.person.cache.get_identity(), cached)
        self.assertEqual(self.person.cache.get_person_profile(uid), cached)
        self.assertEqual(self.person.cache.get_area_members_page("area", 0, 20), page)

        result = await self.person.clear_playing_state()
        self.assertTrue(result.ok)
        self.assertIsNone(self.person.cache.get_identity())
        self.assertIsNone(self.person.cache.get_person_profile(uid))
        self.assertIsNotNone(self.person.cache.get_person_profile("friend"))
        self.assertIsNone(self.person.cache.get_area_members_page("area", 0, 20))
        self.assertEqual(self.person.cache.get_area_members_page("area", 20, 40), other_page)

    async def test_invalid_state_is_rejected_before_sending(self) -> None:
        with self.assertRaisesRegex(TypeError, "uid"):
            await self.person.get_playing_state(123)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "uid"):
            await self.person.get_playing_state("  ")
        with self.assertRaises(ValueError):
            await self.person.set_game_state("  ")
        with self.assertRaises(TypeError):
            await self.person.set_game_state("组队中", game_id=True)
        with self.assertRaises(ValueError):
            await self.person.set_game_state("组队中", game_id=-1)
        with self.assertRaises(ValueError):
            await self.person.set_music_state(" ", "七里香")
        with self.assertRaisesRegex(TypeError, "song"):
            await self.person.set_music_state("QQ音乐", None)  # type: ignore[arg-type]
        self.request.assert_not_awaited()
