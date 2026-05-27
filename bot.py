"""
Discord Music Bot with Lavalink v4
2025년 YouTube 차단 대응 - OAuth2 인증 지원
"""

import discord
from discord.ext import commands
import wavelink
import os
import asyncio
import logging
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# --- Lavalink 4.2+ channelId 호환 패치 ---
# wavelink 3.4.x는 voice PATCH에 channelId를 보내지 않아 Lavalink 4.2+에서 오류 발생.
# 런타임에서 Player 메서드를 패치하여 channelId를 주입한다.

_original_on_voice_state_update = wavelink.Player.on_voice_state_update


async def _patched_on_voice_state_update(self, data, /):
    channel_id = data["channel_id"]
    if channel_id:
        if not hasattr(self, "_voice_state"):
            self._voice_state = {"voice": {}}
        self._voice_state.setdefault("voice", {})["channel_id"] = channel_id
    await _original_on_voice_state_update(self, data)


_original_dispatch_voice_update = wavelink.Player._dispatch_voice_update


async def _patched_dispatch_voice_update(self):
    assert self.guild is not None
    data = self._voice_state["voice"]
    session_id = data.get("session_id")
    token = data.get("token")
    endpoint = data.get("endpoint")
    channel_id = data.get("channel_id")

    if not session_id or not token or not endpoint:
        return

    voice_payload = {"sessionId": session_id, "token": token, "endpoint": endpoint}
    if channel_id:
        voice_payload["channelId"] = channel_id

    try:
        await self.node._update_player(self.guild.id, data={"voice": voice_payload})
    except wavelink.LavalinkException:
        await self.disconnect()
    else:
        self._connection_event.set()

    logging.getLogger("wavelink.player").debug(
        "Player %s is dispatching VOICE_UPDATE.", self.guild.id
    )


wavelink.Player.on_voice_state_update = _patched_on_voice_state_update
wavelink.Player._dispatch_voice_update = _patched_dispatch_voice_update

TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_URI = os.getenv("LAVALINK_URI", "http://localhost:2333")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """봇 시작 시 Lavalink 노드 연결 및 Cog 로드"""

        # Lavalink 노드 설정
        node = wavelink.Node(
            uri=LAVALINK_URI,
            password=LAVALINK_PASSWORD,
        )

        # Lavalink 연결
        await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)

        # Music Cog 로드
        await self.load_extension("cogs.music")

        print(f"[Lavalink] {LAVALINK_URI} 연결 완료")

    async def on_ready(self):
        print(f"[Bot] {self.user.name} 준비 완료!")
        print(f"[Bot] 서버 {len(self.guilds)}개에 연결됨")

        # 슬래시 커맨드 동기화
        try:
            synced = await self.tree.sync()
            print(f"[Bot] 슬래시 커맨드 {len(synced)}개 동기화 완료")
        except Exception as e:
            print(f"[Bot] 동기화 오류: {e}")

        # 상태 메시지 설정
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/재생 으로 음악 재생"
            )
        )

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Lavalink 노드 준비 완료 시"""
        print(f"[Lavalink] 노드 '{payload.node.identifier}' 준비 완료")
        print(f"[Lavalink] 세션 ID: {payload.session_id}")

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """트랙 재생 시작 시 (로그만 출력)"""
        track = payload.track
        print(f"[재생] {track.title}")

    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """트랙 재생 종료 시"""
        player = payload.player

        if not player:
            return

        # queue.get() 안에서 loop/loop_all 분기를 처리하므로
        # if player.queue 로 미리 거르면 반복 모드가 동작하지 않는다.
        try:
            next_track = player.queue.get()
        except wavelink.QueueEmpty:
            await start_disconnect_timer(player)
            return

        await player.play(next_track)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """음성 채널 상태 변경 감지 - 봇 혼자 남으면 퇴장"""

        # 봇 자신의 상태 변경은 무시
        if member.id == self.user.id:
            return

        # 누군가 채널에서 나갔을 때만 체크
        if before.channel is None:
            return

        # 봇이 해당 채널에 있는지 확인
        player = member.guild.voice_client
        if not player or player.channel != before.channel:
            return

        # 채널에 봇 혼자만 남았는지 확인 (봇 제외한 멤버가 0명)
        members = [m for m in before.channel.members if not m.bot]
        if len(members) == 0:
            await player.disconnect()
            print(f"[퇴장] {before.channel.name} 채널에 아무도 없어서 퇴장")


def format_duration(milliseconds: int) -> str:
    """밀리초를 MM:SS 형식으로 변환"""
    seconds = milliseconds // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


async def start_disconnect_timer(player: wavelink.Player, timeout: int = 60):
    """자동 퇴장 타이머"""
    await asyncio.sleep(timeout)

    if player and player.connected and not player.playing:
        await player.disconnect()
        print("[퇴장] 재생할 곡이 없어서 퇴장")


async def main():
    bot = MusicBot()

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
