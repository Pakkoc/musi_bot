"""
Music Cog - Lavalink v4 기반 음악 재생 명령어
"""

import discord
from discord.ext import commands
from discord import app_commands
import wavelink
from typing import Optional, cast


class Music(commands.Cog):
    """음악 재생 관련 명령어"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def format_duration(self, milliseconds: int) -> str:
        """밀리초를 MM:SS 형식으로 변환"""
        seconds = milliseconds // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    async def ensure_voice(self, interaction: discord.Interaction) -> Optional[wavelink.Player]:
        """음성 채널 연결 확인 및 플레이어 반환"""

        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ 먼저 음성 채널에 입장해주세요.",
                ephemeral=True
            )
            return None

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            # 새로 연결
            try:
                player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                player.text_channel = interaction.channel  # 텍스트 채널 저장
                player.autoplay = wavelink.AutoPlayMode.disabled  # 자동재생 비활성화
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ 음성 채널 연결 실패: {e}",
                    ephemeral=True
                )
                return None

        elif player.channel != interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ 봇과 같은 음성 채널에 있어야 합니다.",
                ephemeral=True
            )
            return None

        return player

    @app_commands.command(name="재생", description="음악을 재생합니다 (YouTube, Spotify, SoundCloud 등)")
    @app_commands.describe(검색어="노래 제목, YouTube 링크, Spotify 링크 등")
    async def play(self, interaction: discord.Interaction, 검색어: str):
        """음악 재생"""

        player = await self.ensure_voice(interaction)
        if not player:
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 검색어에 따라 트랙 검색
            tracks = await wavelink.Playable.search(검색어)

            if not tracks:
                await interaction.followup.send("❌ 검색 결과가 없습니다.")
                return

            # 플레이리스트인 경우
            if isinstance(tracks, wavelink.Playlist):
                added = 0
                for track in tracks.tracks:
                    track.requester = interaction.user.mention
                    player.queue.put(track)
                    added += 1

                embed = discord.Embed(
                    title="📋 플레이리스트 추가됨",
                    description=f"**{tracks.name}**",
                    color=0x3498db
                )
                embed.add_field(name="곡 수", value=f"{added}곡", inline=True)
                await interaction.followup.send(embed=embed)

                # 재생 중이 아니면 시작
                if not player.playing:
                    first_track = player.queue.get()
                    await player.play(first_track)

            else:
                # 단일 트랙
                track = tracks[0]
                track.requester = interaction.user.mention

                if player.playing:
                    player.queue.put(track)
                    embed = discord.Embed(
                        title="➕ 대기열에 추가됨",
                        description=f"**[{track.title}]({track.uri})**",
                        color=0x3498db
                    )
                    embed.add_field(name="길이", value=self.format_duration(track.length), inline=True)
                    embed.add_field(name="대기 순서", value=f"{len(player.queue)}번째", inline=True)

                    if track.artwork:
                        embed.set_thumbnail(url=track.artwork)

                    await interaction.followup.send(embed=embed)
                else:
                    await player.play(track)
                    embed = discord.Embed(
                        title="🎵 재생 시작",
                        description=f"**[{track.title}]({track.uri})**",
                        color=0x3498db
                    )
                    embed.add_field(name="길이", value=self.format_duration(track.length), inline=True)

                    if track.artwork:
                        embed.set_thumbnail(url=track.artwork)

                    await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: {e}")

    @app_commands.command(name="스킵", description="현재 재생 중인 곡을 건너뜁니다")
    async def skip(self, interaction: discord.Interaction):
        """스킵"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player or not player.playing:
            await interaction.response.send_message("❌ 재생 중인 곡이 없습니다.", ephemeral=True)
            return

        current_title = player.current.title if player.current else "알 수 없음"
        await player.skip()

        embed = discord.Embed(
            title="⏭️ 스킵",
            description=f"**{current_title}** 건너뜀",
            color=0x3498db
        )

        if player.queue:
            embed.add_field(name="다음 곡", value=player.queue[0].title, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="일시정지", description="음악을 일시정지하거나 다시 재생합니다")
    async def pause(self, interaction: discord.Interaction):
        """일시정지/재개"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        if player.paused:
            await player.pause(False)
            await interaction.response.send_message("▶️ 재생을 재개합니다.", ephemeral=True)
        else:
            await player.pause(True)
            await interaction.response.send_message("⏸️ 일시정지되었습니다.", ephemeral=True)

    @app_commands.command(name="멈춰", description="음악을 멈추고 봇이 퇴장합니다")
    async def stop(self, interaction: discord.Interaction):
        """정지 및 퇴장"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        player.queue.clear()
        await player.disconnect()

        await interaction.response.send_message("👋 음악을 멈추고 퇴장합니다.", ephemeral=True)

    @app_commands.command(name="대기열", description="현재 대기열을 확인합니다")
    async def queue(self, interaction: discord.Interaction):
        """대기열 확인"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(title="🎵 재생 대기열", color=0x3498db)

        # 현재 재생 중인 곡
        if player.current:
            current = player.current
            embed.add_field(
                name="🔊 현재 재생 중",
                value=f"**[{current.title}]({current.uri})**\n길이: {self.format_duration(current.length)}",
                inline=False
            )
        else:
            embed.add_field(name="🔊 현재 재생 중", value="없음", inline=False)

        # 대기열
        if player.queue:
            queue_list = []
            for i, track in enumerate(player.queue[:10], 1):
                queue_list.append(f"`{i}.` **{track.title}** ({self.format_duration(track.length)})")

            queue_text = "\n".join(queue_list)

            if len(player.queue) > 10:
                queue_text += f"\n\n... 외 {len(player.queue) - 10}곡"

            embed.add_field(name=f"📋 대기열 ({len(player.queue)}곡)", value=queue_text, inline=False)
        else:
            embed.add_field(name="📋 대기열", value="비어있음", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="반복", description="반복 재생 모드를 설정합니다")
    @app_commands.describe(모드="반복 모드 선택")
    @app_commands.choices(모드=[
        app_commands.Choice(name="끄기", value="off"),
        app_commands.Choice(name="한 곡 반복", value="one"),
        app_commands.Choice(name="전체 반복", value="all"),
    ])
    async def loop(self, interaction: discord.Interaction, 모드: str):
        """반복 재생"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        if 모드 == "off":
            player.queue.mode = wavelink.QueueMode.normal
            await interaction.response.send_message("➡️ 반복 재생이 꺼졌습니다.", ephemeral=True)
        elif 모드 == "one":
            player.queue.mode = wavelink.QueueMode.loop
            await interaction.response.send_message("🔂 현재 곡을 반복합니다.", ephemeral=True)
        elif 모드 == "all":
            player.queue.mode = wavelink.QueueMode.loop_all
            await interaction.response.send_message("🔁 전체 대기열을 반복합니다.", ephemeral=True)

    @app_commands.command(name="볼륨", description="볼륨을 조절합니다 (0-100)")
    @app_commands.describe(볼륨="볼륨 크기 (0-100)")
    async def volume(self, interaction: discord.Interaction, 볼륨: int):
        """볼륨 조절"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        볼륨 = max(0, min(100, 볼륨))  # 0-100 범위 제한
        await player.set_volume(볼륨)

        await interaction.response.send_message(f"🔊 볼륨을 {볼륨}%로 설정했습니다.", ephemeral=True)

    @app_commands.command(name="셔플", description="대기열을 섞습니다")
    async def shuffle(self, interaction: discord.Interaction):
        """셔플"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        if not player.queue:
            await interaction.response.send_message("❌ 대기열이 비어있습니다.", ephemeral=True)
            return

        player.queue.shuffle()
        await interaction.response.send_message(f"🔀 대기열을 섞었습니다! ({len(player.queue)}곡)", ephemeral=True)

    @app_commands.command(name="삭제", description="대기열에서 특정 곡을 삭제합니다")
    @app_commands.describe(번호="삭제할 곡의 번호 (대기열에서)")
    async def remove(self, interaction: discord.Interaction, 번호: int):
        """대기열에서 곡 삭제"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player:
            await interaction.response.send_message("❌ 봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        if 번호 < 1 or 번호 > len(player.queue):
            await interaction.response.send_message(
                f"❌ 올바른 번호를 입력해주세요. (1-{len(player.queue)})",
                ephemeral=True
            )
            return

        removed = player.queue[번호 - 1]
        del player.queue[번호 - 1]

        await interaction.response.send_message(f"🗑️ **{removed.title}** 삭제됨", ephemeral=True)

    @app_commands.command(name="현재곡", description="현재 재생 중인 곡 정보를 보여줍니다")
    async def nowplaying(self, interaction: discord.Interaction):
        """현재 재생 곡 정보"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player or not player.current:
            await interaction.response.send_message("❌ 재생 중인 곡이 없습니다.", ephemeral=True)
            return

        track = player.current
        position = player.position  # 현재 재생 위치 (밀리초)

        # 진행률 바 생성
        progress = int((position / track.length) * 20)
        bar = "▓" * progress + "░" * (20 - progress)

        embed = discord.Embed(
            title="🎵 현재 재생 중",
            description=f"**[{track.title}]({track.uri})**",
            color=0x3498db
        )

        embed.add_field(
            name="진행",
            value=f"`{self.format_duration(position)}` {bar} `{self.format_duration(track.length)}`",
            inline=False
        )

        if hasattr(track, 'requester'):
            embed.add_field(name="요청자", value=track.requester, inline=True)

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        # 반복 모드 표시
        mode_text = {
            wavelink.QueueMode.normal: "끔",
            wavelink.QueueMode.loop: "🔂 한 곡",
            wavelink.QueueMode.loop_all: "🔁 전체"
        }
        embed.add_field(name="반복", value=mode_text.get(player.queue.mode, "끔"), inline=True)
        embed.add_field(name="볼륨", value=f"{player.volume}%", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="탐색", description="곡의 특정 위치로 이동합니다")
    @app_commands.describe(초="이동할 위치 (초 단위)")
    async def seek(self, interaction: discord.Interaction, 초: int):
        """특정 위치로 이동"""

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if not player or not player.current:
            await interaction.response.send_message("❌ 재생 중인 곡이 없습니다.", ephemeral=True)
            return

        position_ms = 초 * 1000
        max_position = player.current.length

        if position_ms < 0 or position_ms > max_position:
            await interaction.response.send_message(
                f"❌ 0초에서 {max_position // 1000}초 사이로 입력해주세요.",
                ephemeral=True
            )
            return

        await player.seek(position_ms)
        await interaction.response.send_message(f"⏩ {self.format_duration(position_ms)}로 이동했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
