# cogs/management.py

import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# events.py 파일에 있는 JoinView를 가져옵니다.
from .events import JoinView

class Management(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Cog 내부의 모든 슬래시 커맨드 에러를 처리하는 핸들러
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        else:
            print(f"An error occurred in a command: {error}")
            # 이미 응답이 보내진 경우 followup으로, 아닌 경우 response로 에러 메시지를 보냅니다.
            if interaction.response.is_done():
                await interaction.followup.send("명령어 실행 중 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("명령어 실행 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="멤버공개", description="다음 내전에 참여할 10명의 멤버 목록을 보여줍니다. (관리자용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def show_members_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
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
            if not target_channel:
                await interaction.response.send_message("❌ 해당 채널을 찾을 수 없습니다.", ephemeral=True); return
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

    # --- 운영자 참여 관련 명령어 ---
    
    # 백그라운드에서 실제 데이터베이스 작업을 처리할 별도의 함수
    async def run_admin_join_task(self, interaction: discord.Interaction, admin_user: discord.User):
        admin_id = admin_user.id
        try:
            player_info = self.bot.supabase.table('players').select('id').eq('id', admin_id).execute().data
            if not player_info:
                await interaction.channel.send(f"⚠️ {admin_user.mention}님, `/정보등록`을 먼저 해야 이 기능을 사용할 수 있습니다.")
                return

            # 1. 운영자가 이미 대기열에 있다면, 우선 현재 위치에서 삭제
            self.bot.supabase.table('queue').delete().eq('player_id', admin_id).execute()

            # 2. [수정] 현재 1순위 멤버의 신청 시간을 기준으로, 그것보다 1초 빠르게 운영자를 삽입
            first_in_queue = self.bot.supabase.table('queue').select('created_at').order('created_at').limit(1).execute().data
        
            if first_in_queue:
                from datetime import datetime, timedelta
                # 현재 1순위의 시간을 가져와서 1초를 뺀다
                first_user_time_str = first_in_queue[0]['created_at']
                first_user_time = datetime.fromisoformat(first_user_time_str)
                admin_priority_time = first_user_time - timedelta(seconds=1)
                # DB에 넣기 위해 다시 문자열로 변환
                priority_timestamp = admin_priority_time.isoformat()
            else:
                # 대기열에 아무도 없다면 지금 시간으로 바로 등록
                from datetime import datetime, timezone
                priority_timestamp = datetime.now(timezone.utc).isoformat()

            self.bot.supabase.table('queue').insert({
                'player_id': admin_id,
                'created_at': priority_timestamp
            }).execute()
        
            # 3. 작업이 모두 끝난 후, 채널에 새로운 메시지를 보내 결과를 알립니다.
            await interaction.channel.send(f"✅ {admin_user.mention} 님을 대기열 1순위로 등록했습니다. `/멤버공개`로 최종 명단을 확인하세요.")

        except Exception as e:
            print(f"운영자 우선 참여 백그라운드 작업 오류: {e}")
            await interaction.channel.send(f"❌ {admin_user.mention}님, 운영자 우선 참여 처리 중 오류가 발생했습니다.")

    @app_commands.command(name="운영자참여", description="본인을 대기열 1순위로 등록하여 내전에 즉시 참여합니다. (관리자용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_join_priority_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"⏳ {interaction.user.mention} 님의 우선 참여 요청을 접수했습니다. 잠시 후 처리됩니다.", ephemeral=True)
        asyncio.create_task(self.run_admin_join_task(interaction, interaction.user))
    
    @app_commands.command(name="db테스트", description="Supabase DB 쓰기 권한을 테스트합니다. (관리자용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def db_test_command(self, interaction: discord.Interaction):
        try:
            # 1. 즉시 응답하여 시간 초과를 방지합니다.
            await interaction.response.send_message("⏳ 데이터베이스 쓰기 테스트를 시작합니다...")

            # 2. test_logs 테이블에 간단한 데이터를 하나 추가(INSERT)합니다.
            log_entry = {'log_message': 'Test from Raspberry Pi'}
            response = self.bot.supabase.table('test_logs').insert(log_entry).execute()

            # 3. 성공 여부에 따라 원래 보냈던 메시지를 수정합니다.
            if response.data:
                await interaction.edit_original_response(content="✅ 데이터베이스 쓰기 테스트 성공!")
            else:
                # 데이터가 비어있으면 오류로 간주
                raise Exception("Supabase 응답에 데이터가 없습니다.")

        except Exception as e:
            print(f"[DB TEST ERROR] {e}")
            await interaction.edit_original_response(content=f"❌ 데이터베이스 쓰기 테스트 실패! 로그를 확인해주세요.")

# 이 Cog를 봇에 추가하기 위한 필수 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))