# cogs/management.py

import discord
from discord import app_commands
from discord.ext import commands

# events.py 파일에 있는 JoinView를 가져옵니다.
from .events import JoinView

class Management(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Cog 내부의 모든 슬래시 커맨드 에러를 처리하는 핸들러
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            # ephemeral=True를 사용하면 보냈다는 응답을 따로 할 필요가 없습니다.
            await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        else:
            print(f"An error occurred in a command: {error}")
            if interaction.response.is_done():
                await interaction.followup.send("명령어 실행 중 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("명령어 실행 중 오류가 발생했습니다.", ephemeral=True)


    @app_commands.command(name="멤버공개", description="다음 내전에 참여할 10명의 멤버 목록을 보여줍니다. (관리자용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def show_members_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            # (주의) supabase는 self.bot.supabase 로 접근해야 합니다.
            query = self.bot.supabase.table('queue').select('players(id, valorant_nickname, highest_tier, current_tier)').order('created_at').limit(10)
            response = query.execute()
            members = response.data
            count_response = self.bot.supabase.table('queue').select('player_id', count='exact').execute()
            total_count = count_response.count
            if not members:
                await interaction.followup.send("현재 대기 중인 멤버가 없습니다."); return
            embed = discord.Embed(title="⚔️ 다음 내전 참여 예정 멤버", description=f"총 {total_count}명이 대기 중입니다.", color=discord.Color.gold())
            member_list = []
            for idx, member_data in enumerate(members):
                player = member_data['players']
                if player:
                    try:
                        user = await self.bot.fetch_user(player['id']); mention = user.mention
                    except discord.NotFound:
                        mention = f"ID: {player['id']} (찾을 수 없음)"
                    h_tier = player.get('highest_tier') or '정보없음'
                    c_tier = player.get('current_tier') or '정보없음'
                    line = f"`{idx + 1:2d}` {mention} | `{player['valorant_nickname']}` (`{h_tier}` / `{c_tier}`)"
                    member_list.append(line)
            embed.add_field(name="참여자 목록 (선착순 10명)", value="\n".join(member_list), inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"멤버 공개 오류: {e}"); await interaction.followup.send("❌ 멤버 목록을 불러오는 중 오류가 발생했습니다.")

    @app_commands.command(name="내전모집", description="내전 대기열 참여 메시지를 보냅니다. (관리자용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def recruit_command(self, interaction: discord.Interaction, 제목: str, 내용: str = "아래 버튼을 눌러 내전 대기열에 참여하세요!"):
        embed = discord.Embed(title=f"⚔️ {제목}", description=내용, color=discord.Color.blue())
        embed.set_footer(text="이 버튼은 항상 활성화되어 있으며, 언제든 눌러 대기열에 참여할 수 있습니다.")
        # (주의) JoinView를 생성할 때 self.bot를 전달해줍니다.
        await interaction.response.send_message(embed=embed, view=JoinView(self.bot))

    @app_commands.command(name="멤버제외", description="특정 유저를 내전 대기열에서 제외합니다. (관리자용)")
    @app_commands.describe(유저="대기열에서 제외할 유저를 선택하세요.")
    @app_commands.checks.has_permissions(administrator=True)
    async def kick_member_command(self, interaction: discord.Interaction, 유저: discord.User):
        await interaction.response.defer(ephemeral=True)
        try:
            target_id = 유저.id
            in_queue = self.bot.supabase.table('queue').select('player_id').eq('player_id', target_id).execute().data
            if not in_queue:
                await interaction.followup.send(f"{유저.mention} 님은 현재 대기열에 없습니다.", ephemeral=True); return
            self.bot.supabase.table('queue').delete().eq('player_id', target_id).execute()
            await interaction.followup.send(f"✅ {유저.mention} 님을 대기열에서 제외했습니다.", ephemeral=True)
        except Exception as e:
            print(f"멤버 제외 오류: {e}"); await interaction.followup.send("❌ 멤버 제외 처리 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="내전시작", description="대기열 상위 인원에게 내전 시작 DM을 보냅니다. (관리자용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def start_civil_war_command(self, interaction: discord.Interaction, 공지내용: str = "내전이 시작되었습니다! 지정된 음성 채널로 모여주세요."):
        await interaction.response.defer()
        try:
            team_response = self.bot.supabase.table('queue').select('players(id)').order('created_at').limit(10).execute()
            members = team_response.data
            if not members:
                await interaction.followup.send(f"❌ 대기열에 멤버가 없습니다.", ephemeral=True); return
            sent_users, failed_users = [], []
            embed = discord.Embed(title="🔔 내전 시작 알림", description=공지내용, color=discord.Color.green())
            for member_data in members:
                player = member_data['players']
                if player:
                    user = await self.bot.fetch_user(player['id'])
                    try:
                        await user.send(embed=embed); sent_users.append(user.mention)
                    except discord.Forbidden:
                        failed_users.append(user.mention)
            result_embed = discord.Embed(title="✅ 내전 시작 알림 발송 완료", description=f"총 {len(members)}명에게 DM 발송을 시도했습니다.", color=discord.Color.blue())
            result_embed.add_field(name="✉️ DM 발송 성공", value="\n".join(sent_users) if sent_users else "없음", inline=False)
            if failed_users:
                result_embed.add_field(name="⚠️ DM 발송 실패 (DM을 차단한 유저)", value="\n".join(failed_users), inline=False)
            await interaction.followup.send(embed=result_embed)
        except Exception as e:
            print(f"내전 시작 오류: {e}"); await interaction.followup.send("❌ 내전 시작 처리 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="모집마감", description="특정 내전 모집 메시지의 참여 버튼을 비활성화합니다. (관리자용)")
    @app_commands.describe(메시지링크="버튼을 비활성화할 모집 공고 메시지의 링크")
    @app_commands.checks.has_permissions(administrator=True)
    async def close_recruit_command(self, interaction: discord.Interaction, 메시지링크: str):
        try:
            parts = 메시지링크.split('/'); channel_id, message_id = int(parts[-2]), int(parts[-1])
            target_channel = self.bot.get_channel(channel_id)
            target_message = await target_channel.fetch_message(message_id)
            disabled_view = JoinView(self.bot)
            for item in disabled_view.children:
                if isinstance(item, discord.ui.Button): item.disabled = True
            await target_message.edit(view=disabled_view)
            await interaction.response.send_message("✅ '내전 참여' 버튼을 비활성화했습니다.", ephemeral=True)
        except (discord.NotFound, ValueError, AttributeError): await interaction.response.send_message("❌ 메시지를 찾을 수 없거나 링크가 잘못되었습니다.", ephemeral=True)
        except Exception as e:
            print(f"모집 마감 처리 오류: {e}"); await interaction.response.send_message("❌ 모집 마감 처리 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="내전종료", description="진행된 내전을 종료하고, 참여한 인원을 대기열에서 제외합니다. (관리자용)")
    @app_commands.describe(참여인원="실제 내전에 참여한 인원 수를 입력하세요.")
    @app_commands.checks.has_permissions(administrator=True)
    async def end_civil_war_command(self, interaction: discord.Interaction, 참여인원: int):
        await interaction.response.defer(ephemeral=True)
        if 참여인원 <= 0:
            await interaction.followup.send("❌ 참여인원은 1 이상의 숫자여야 합니다.", ephemeral=True); return
        try:
            current_players_response = self.bot.supabase.table('queue').select('player_id').order('created_at').limit(참여인원).execute()
            if not current_players_response.data: await interaction.followup.send("종료할 내전 대기열이 없습니다.", ephemeral=True); return
            player_ids_to_remove = [player['player_id'] for player in current_players_response.data]
            self.bot.supabase.table('queue').delete().in_('player_id', player_ids_to_remove).execute()
            await interaction.followup.send(f"✅ 내전이 종료되었습니다. 참여한 {len(player_ids_to_remove)}명을 대기열에서 제외했습니다.", ephemeral=True)
            next_player_response = self.bot.supabase.table('queue').select('player_id').order('created_at').limit(1).execute()
            if next_player_response.data:
                next_user = await self.bot.fetch_user(next_player_response.data[0]['player_id'])
                if next_user: await interaction.channel.send(f"🔔 다음 내전 대기 1순위는 {next_user.mention} 님입니다!")
        except Exception as e:
            print(f"내전 종료 처리 오류: {e}"); await interaction.followup.send("❌ 내전 종료 처리 중 오류가 발생했습니다.", ephemeral=True)

# 이 Cog를 봇에 추가하기 위한 필수 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))