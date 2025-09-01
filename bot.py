# bot.py

import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from supabase import create_client, Client

# --- 1. 환경 변수 로드 및 클라이언트 초기화 ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# 멤버 정보를 원활하게 가져오기 위해 members 인텐트를 활성화합니다.
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)


# --- 2. 봇 이벤트 핸들러 정의 ---
@bot.event
async def on_ready():
    print(f'✅ {bot.user.name}(으)로 성공적으로 로그인했습니다!')
    print(f'봇 ID: {bot.user.id}')
    print('---------------------------------')
    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)}개의 슬래시 커맨드를 동기화했습니다.')
    except Exception as e:
        print(f'커맨드 동기화 중 오류 발생: {e}')

class JoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="내전 대기열 참여", style=discord.ButtonStyle.success, custom_id="join_civil_war_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)
        try:
            player_info = supabase.table('players').select('id').eq('id', user_id).execute().data
            if not player_info:
                await interaction.followup.send("⚠️ 먼저 `/정보등록`으로 정보를 등록해야 참여할 수 있습니다.", ephemeral=True)
                return
            in_queue = supabase.table('queue').select('player_id').eq('player_id', user_id).execute().data
            if in_queue:
                await interaction.followup.send("이미 내전 대기열에 등록되어 있습니다.", ephemeral=True)
                return
            supabase.table('queue').insert({'player_id': user_id}).execute()
            queue_response = supabase.table('queue').select('player_id', count='exact').order('created_at').execute()
            total_in_queue = queue_response.count
            await interaction.followup.send(f"✅ 내전 대기열 참여 신청이 완료되었습니다! 현재 대기 순서는 {total_in_queue}번입니다.", ephemeral=True)
        except Exception as e:
            print(f"내전 참여 처리 오류: {e}")
            await interaction.followup.send("❌ 내전 참여 처리 중 오류가 발생했습니다.", ephemeral=True)

@bot.event
async def setup_hook():
    bot.add_view(JoinView())


# --- 3. 핵심 기능 구현 ---

# --- 3-1. 개인 정보 관련 기능 ---
class PlayerInfoModal(discord.ui.Modal, title="내전 참여 정보 등록"):
    valorant_nickname = discord.ui.TextInput(label="발로란트 닉네임#태그", placeholder="예시) 챌린저#KR1", required=True)
    chzzk_nickname = discord.ui.TextInput(label="치지직 닉네임", placeholder="사용하는 치지직 닉네임을 입력하세요.", required=True)
    highest_tier = discord.ui.TextInput(label="최고 티어", placeholder="예시) 다이아몬드 1", required=True)
    current_tier = discord.ui.TextInput(label="현재 티어", placeholder="예시) 플래티넘 3", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            response = supabase.table('players').upsert({'id': interaction.user.id, 'valorant_nickname': self.valorant_nickname.value, 'chzzk_nickname': self.chzzk_nickname.value, 'highest_tier': self.highest_tier.value, 'current_tier': self.current_tier.value}).execute()
            if response.data: await interaction.response.send_message("✅ 정보가 성공적으로 등록(수정)되었습니다!", ephemeral=True)
            else: raise Exception("Supabase 응답에 데이터가 없습니다.")
        except Exception as e:
            print(f"DB 저장 오류: {e}"); await interaction.response.send_message("❌ 정보를 저장하는 중 오류가 발생했습니다.", ephemeral=True)

@bot.tree.command(name="정보등록", description="내전 참여를 위한 정보를 등록하거나 수정합니다.")
async def register_command(interaction: discord.Interaction):
    await interaction.response.send_modal(PlayerInfoModal())

@bot.tree.command(name="내순서", description="현재 나의 내전 대기열 순서를 확인합니다.")
async def my_rank_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        queue_response = supabase.table('queue').select('player_id').order('created_at').execute()
        if not queue_response.data:
            await interaction.followup.send("현재 대기열이 비어있습니다.", ephemeral=True); return
        all_player_ids = [player['player_id'] for player in queue_response.data]
        if interaction.user.id in all_player_ids:
            rank = all_player_ids.index(interaction.user.id) + 1
            await interaction.followup.send(f"현재 회원님의 대기 순서는 **{rank}번**입니다.", ephemeral=True)
        else:
            await interaction.followup.send("회원님은 현재 대기열에 없습니다. '내전 참여' 버튼을 눌러주세요.", ephemeral=True)
    except Exception as e:
        print(f"내 순서 확인 오류: {e}"); await interaction.followup.send("❌ 순서 확인 중 오류가 발생했습니다.", ephemeral=True)


# --- 3-2. 내전 관리 기능 (관리자용) ---
@bot.tree.command(name="멤버공개", description="다음 내전에 참여할 10명의 멤버 목록을 보여줍니다. (관리자용)")
@app_commands.checks.has_permissions(administrator=True)
async def show_members_command(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        query = supabase.table('queue').select('players(id, valorant_nickname, highest_tier, current_tier)').order('created_at').limit(10)
        response = query.execute()
        members = response.data
        count_response = supabase.table('queue').select('player_id', count='exact').execute()
        total_count = count_response.count
        if not members:
            await interaction.followup.send("현재 대기 중인 멤버가 없습니다."); return
        embed = discord.Embed(title="⚔️ 다음 내전 참여 예정 멤버", description=f"총 {total_count}명이 대기 중입니다.", color=discord.Color.gold())
        member_list = []
        for idx, member_data in enumerate(members):
            player = member_data['players']
            if player:
                try:
                    user = await bot.fetch_user(player['id']); mention = user.mention
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

@bot.tree.command(name="내전모집", description="내전 대기열 참여 메시지를 보냅니다. (관리자용)")
@app_commands.checks.has_permissions(administrator=True)
async def recruit_command(interaction: discord.Interaction, 제목: str, 내용: str = "아래 버튼을 눌러 내전 대기열에 참여하세요!"):
    embed = discord.Embed(title=f"⚔️ {제목}", description=내용, color=discord.Color.blue())
    embed.set_footer(text="이 버튼은 항상 활성화되어 있으며, 언제든 눌러 대기열에 참여할 수 있습니다.")
    await interaction.response.send_message(embed=embed, view=JoinView())

# 🔽🔽🔽 [신규] 멤버 제외 기능 🔽🔽🔽
@bot.tree.command(name="멤버제외", description="특정 유저를 내전 대기열에서 제외합니다. (관리자용)")
@app_commands.describe(유저="대기열에서 제외할 유저를 선택하세요.")
@app_commands.checks.has_permissions(administrator=True)
async def kick_member_command(interaction: discord.Interaction, 유저: discord.User):
    await interaction.response.defer(ephemeral=True)
    try:
        target_id = 유저.id
        in_queue = supabase.table('queue').select('player_id').eq('player_id', target_id).execute().data
        if not in_queue:
            await interaction.followup.send(f"{유저.mention} 님은 현재 대기열에 없습니다.", ephemeral=True)
            return
        supabase.table('queue').delete().eq('player_id', target_id).execute()
        await interaction.followup.send(f"✅ {유저.mention} 님을 대기열에서 제외했습니다.", ephemeral=True)
    except Exception as e:
        print(f"멤버 제외 오류: {e}"); await interaction.followup.send("❌ 멤버 제외 처리 중 오류가 발생했습니다.", ephemeral=True)

# 🔽🔽🔽 [수정] 내전 시작 기능 🔽🔽🔽
@bot.tree.command(name="내전시작", description="대기열 상위 인원에게 내전 시작 DM을 보냅니다. (관리자용)")
@app_commands.checks.has_permissions(administrator=True)
async def start_civil_war_command(interaction: discord.Interaction, 공지내용: str = "내전이 시작되었습니다! 지정된 음성 채널로 모여주세요."):
    await interaction.response.defer()
    try:
        team_response = supabase.table('queue').select('players(id)').order('created_at').limit(10).execute()
        members = team_response.data
        
        # 10명인지 확인하는 부분을 제거하고, 1명도 없는지만 확인합니다.
        if not members:
            await interaction.followup.send(f"❌ 대기열에 멤버가 없습니다.", ephemeral=True)
            return
        
        sent_users = []
        failed_users = []
        
        embed = discord.Embed(title="🔔 내전 시작 알림", description=공지내용, color=discord.Color.green())
        
        for member_data in members:
            player = member_data['players']
            if player:
                user = await bot.fetch_user(player['id'])
                try:
                    await user.send(embed=embed)
                    sent_users.append(user.mention)
                except discord.Forbidden:
                    failed_users.append(user.mention)
        
        result_embed = discord.Embed(title="✅ 내전 시작 알림 발송 완료", description=f"총 {len(sent_users) + len(failed_users)}명에게 DM 발송을 시도했습니다.", color=discord.Color.blue())
        result_embed.add_field(name="✉️ DM 발송 성공", value="\n".join(sent_users) if sent_users else "없음", inline=False)
        if failed_users:
            result_embed.add_field(name="⚠️ DM 발송 실패 (DM을 차단한 유저)", value="\n".join(failed_users), inline=False)
        
        await interaction.followup.send(embed=result_embed)

    except Exception as e:
        print(f"내전 시작 오류: {e}"); await interaction.followup.send("❌ 내전 시작 처리 중 오류가 발생했습니다.", ephemeral=True)


@bot.tree.command(name="모집마감", description="특정 내전 모집 메시지의 참여 버튼을 비활성화합니다. (관리자용)")
@app_commands.describe(메시지링크="버튼을 비활성화할 모집 공고 메시지의 링크")
@app_commands.checks.has_permissions(administrator=True)
async def close_recruit_command(interaction: discord.Interaction, 메시지링크: str):
    try:
        parts = 메시지링크.split('/'); channel_id, message_id = int(parts[-2]), int(parts[-1])
        target_channel = bot.get_channel(channel_id)
        target_message = await target_channel.fetch_message(message_id)
        disabled_view = JoinView()
        for item in disabled_view.children:
            if isinstance(item, discord.ui.Button): item.disabled = True
        await target_message.edit(view=disabled_view)
        await interaction.response.send_message("✅ '내전 참여' 버튼을 비활성화했습니다.", ephemeral=True)
    except (discord.NotFound, ValueError, AttributeError): await interaction.response.send_message("❌ 메시지를 찾을 수 없거나 링크가 잘못되었습니다.", ephemeral=True)
    except Exception as e:
        print(f"모집 마감 처리 오류: {e}"); await interaction.response.send_message("❌ 모집 마감 처리 중 오류가 발생했습니다.", ephemeral=True)

# 🔽🔽🔽 [수정] 내전 종료 기능 🔽🔽🔽
@bot.tree.command(name="내전종료", description="진행된 내전을 종료하고, 참여한 인원을 대기열에서 제외합니다. (관리자용)")
@app_commands.describe(참여인원="실제 내전에 참여한 인원 수를 입력하세요.")
@app_commands.checks.has_permissions(administrator=True)
async def end_civil_war_command(interaction: discord.Interaction, 참여인원: int):
    await interaction.response.defer(ephemeral=True)
    
    if 참여인원 <= 0:
        await interaction.followup.send("❌ 참여인원은 1 이상의 숫자여야 합니다.", ephemeral=True); return
        
    try:
        # 입력받은 '참여인원' 수 만큼 대기열에서 가져옵니다.
        current_players_response = supabase.table('queue').select('player_id').order('created_at').limit(참여인원).execute()
        if not current_players_response.data: await interaction.followup.send("종료할 내전 대기열이 없습니다.", ephemeral=True); return
        
        player_ids_to_remove = [player['player_id'] for player in current_players_response.data]
        supabase.table('queue').delete().in_('player_id', player_ids_to_remove).execute()
        
        await interaction.followup.send(f"✅ 내전이 종료되었습니다. 참여한 {len(player_ids_to_remove)}명을 대기열에서 제외했습니다.", ephemeral=True)
        
        next_player_response = supabase.table('queue').select('player_id').order('created_at').limit(1).execute()
        if next_player_response.data:
            next_user = await bot.fetch_user(next_player_response.data[0]['player_id'])
            if next_user: await interaction.channel.send(f"🔔 다음 내전 대기 1순위는 {next_user.mention} 님입니다!")
    except Exception as e:
        print(f"내전 종료 처리 오류: {e}"); await interaction.followup.send("❌ 내전 종료 처리 중 오류가 발생했습니다.", ephemeral=True)

# 관리자 명령어 에러 핸들러
@recruit_command.error
@close_recruit_command.error
@end_civil_war_command.error
@kick_member_command.error # 신규
@start_civil_war_command.error # 신규
async def admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions): await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
    else: await interaction.response.send_message(f"오류가 발생했습니다: {error}", ephemeral=True)


# --- 4. 봇 실행 ---
try:
    bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure:
    print("❌ 디스코드 토큰이 잘못되었습니다. .env 파일을 확인해주세요.")
except Exception as e:
    print(f"❌ 봇 실행 중 알 수 없는 오류 발생: {e}")