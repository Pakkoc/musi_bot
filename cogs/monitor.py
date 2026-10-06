"""
재생 장애 감지 및 관리자 DM 알림
- 재생 실패(TrackException) 즉시: 채널 안내 + 관리자 DM
- 매일 오전 6시(KST): YouTube/Spotify 곡을 실제로 재생해 보는 자동 점검, 실패 시 관리자 DM

알림 대상: .env의 OWNER_ID(디스코드 사용자 ID), 없으면 Discord 앱 소유자.
"""

import asyncio
import datetime
import json
import os
import time

import aiohttp
import discord
import wavelink
from discord.ext import commands, tasks

KST = datetime.timezone(datetime.timedelta(hours=9))
LAVALINK_URI = os.getenv("LAVALINK_URI", "http://localhost:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

# 점검 대상: (이름, Lavalink identifier)
HEALTH_CHECKS = [
    # 일부 인기 영상(예: dQw4w9WgXcQ)은 로그인 없이도 재생돼 장애를 놓치므로,
    # 2026-10 장애 때 실제로 실패했던 영상 + 일반 검색 결과로 점검한다.
    ("YouTube 링크", "https://www.youtube.com/watch?v=xDfjtE05KJY"),
    ("YouTube 검색", "ytsearch:요네즈 켄시 JANE DOE"),
    ("Spotify", "spsearch:아이유 밤편지"),
]

# 같은 장애로 DM이 폭주하지 않도록 즉시 알림 최소 간격
ALERT_COOLDOWN_SEC = 600

TROUBLESHOOT = (
    "확인 순서:\n"
    "1. `pm2 logs lavalink` 에서 `All clients failed` 원인 확인\n"
    "2. `docker ps` 로 yt-cipher 컨테이너 상태 확인 → `cd yt-cipher && docker compose pull && docker compose up -d`\n"
    "3. youtube-source 신버전 확인: https://github.com/lavalink-devs/youtube-source/releases"
)


async def check_playback(identifier: str, timeout: float = 20.0) -> str | None:
    """봇과 별개의 Lavalink 세션으로 곡을 실제로 재생해 본다.
    음성 연결 없이도 스트림 URL 해석/오픈까지는 진행되므로 YouTube 차단을 감지할 수 있다.
    성공 시 None, 실패 시 사유 문자열 반환."""
    headers = {"Authorization": LAVALINK_PASSWORD, "User-Id": "1", "Client-Name": "musi-healthcheck"}
    base = LAVALINK_URI.rstrip("/")
    ws_url = base.replace("http", "ws", 1) + "/v4/websocket"
    guild_id = "1"  # 가짜 길드 ID (실제 서버와 충돌하지 않음)

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.ws_connect(ws_url) as ws:
                ready = json.loads((await ws.receive(timeout=10)).data)
                session_id = ready["sessionId"]

                async with session.get(f"{base}/v4/loadtracks", params={"identifier": identifier}) as r:
                    result = await r.json()
                load_type, data = result["loadType"], result["data"]
                if load_type == "search" and data:
                    encoded = data[0]["encoded"]
                elif load_type == "track":
                    encoded = data["encoded"]
                else:
                    return f"곡 불러오기 실패 (loadType={load_type}): {str(data)[:200]}"

                await session.patch(
                    f"{base}/v4/sessions/{session_id}/players/{guild_id}",
                    json={"track": {"encoded": encoded}},
                )

                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    msg = await ws.receive(timeout=deadline - time.monotonic())
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    event = json.loads(msg.data)
                    if event.get("op") != "event":
                        continue
                    if event["type"] in ("TrackExceptionEvent", "TrackStuckEvent"):
                        exc = event.get("exception") or {}
                        return exc.get("message", event["type"])[:1500]
                    if event["type"] == "TrackEndEvent" and event.get("reason") == "loadFailed":
                        return "재생 실패 (loadFailed)"
                # 제한 시간 동안 예외가 없으면 스트림이 정상적으로 열린 것
                return None
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        return f"Lavalink 연결/요청 오류: {type(e).__name__}: {e}"


class Monitor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_alert = 0.0
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    async def _get_owner(self) -> discord.User | None:
        owner_id = os.getenv("OWNER_ID")
        if owner_id:
            return await self.bot.fetch_user(int(owner_id))
        app = await self.bot.application_info()
        return app.team.owner if app.team else app.owner

    async def notify_owner(self, content: str):
        try:
            owner = await self._get_owner()
            if owner:
                await owner.send(content[:2000])
        except Exception as e:
            print(f"[알림] 관리자 DM 전송 실패: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        message = (payload.exception or {}).get("message", "알 수 없는 오류")
        title = payload.track.title if payload.track else "?"
        print(f"[재생 실패] {title}: {message.splitlines()[0] if message else ''}")

        player = payload.player
        channel = getattr(player, "text_channel", None) if player else None
        if channel:
            try:
                await channel.send(f"⚠️ **{title}** 재생에 실패했어요. 관리자에게 알렸어요.")
            except discord.HTTPException:
                pass

        now = time.monotonic()
        if now - self._last_alert < ALERT_COOLDOWN_SEC:
            return
        self._last_alert = now
        guild = player.guild.name if player and player.guild else "?"
        await self.notify_owner(
            f"🚨 **뮤지 재생 실패** (서버: {guild})\n곡: {title}\n```\n{message[:1200]}\n```\n{TROUBLESHOOT}"
        )

    async def run_health_check(self) -> list[tuple[str, str]]:
        failures = []
        for name, identifier in HEALTH_CHECKS:
            error = await check_playback(identifier)
            print(f"[점검] {name}: {'정상' if error is None else '실패'}")
            if error:
                failures.append((name, error))
        return failures

    @tasks.loop(time=datetime.time(hour=6, minute=0, tzinfo=KST))
    async def daily_check(self):
        failures = await self.run_health_check()
        if failures:
            details = "\n".join(f"**{name}**\n```\n{err[:700]}\n```" for name, err in failures)
            await self.notify_owner(f"🚨 **뮤지 정기 점검 실패** (오전 6시)\n{details}\n{TROUBLESHOOT}")

    @daily_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Monitor(bot))
