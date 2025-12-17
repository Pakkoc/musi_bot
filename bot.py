"""
Discord Music Bot with Lavalink v4
2025년 YouTube 차단 대응 - OAuth2 인증 지원
"""

import discord
from discord.ext import commands
import wavelink
import os
import asyncio
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

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

        # 다음 곡 재생 (큐에 있는 경우)
        if player.queue:
            next_track = player.queue.get()
            await player.play(next_track)
        else:
            # 큐가 비었으면 자동 퇴장 타이머 시작
            await start_disconnect_timer(player)

    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        """플레이어가 비활성 상태일 때 (채널에 혼자 남음)"""
        await player.disconnect()
        print("[퇴장] 채널에 아무도 없어서 퇴장")


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
