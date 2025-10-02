# cogs/registration.py

import discord
from discord import app_commands
from discord.ext import commands

# 정보 등록을 위한 팝업(Modal) 클래스
class PlayerInfoModal(discord.ui.Modal, title="내전 참여 정보 등록"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    valorant_nickname = discord.ui.TextInput(label="발로란트 닉네임#태그", placeholder="예시) 챌린저#KR1", required=True)
    chzzk_nickname = discord.ui.TextInput(label="치지직 닉네임", placeholder="사용하는 치지직 닉네임을 입력하세요.", required=True)
    highest_tier = discord.ui.TextInput(label="최고 티어", placeholder="예시) 다이아몬드 1", required=True)
    current_tier = discord.ui.TextInput(label="현재 티어", placeholder="예시) 플래티넘 3", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            response = self.bot.supabase.table('players').upsert({'id': interaction.user.id, 'valorant_nickname': self.valorant_nickname.value, 'chzzk_nickname': self.chzzk_nickname.value, 'highest_tier': self.highest_tier.value, 'current_tier': self.current_tier.value}).execute()
            if response.data: await interaction.response.send_message("✅ 정보가 성공적으로 등록(수정)되었습니다!", ephemeral=True)
            else: raise Exception("Supabase 응답에 데이터가 없습니다.")
        except Exception as e:
            print(f"DB 저장 오류: {e}"); await interaction.response.send_message("❌ 정보를 저장하는 중 오류가 발생했습니다.", ephemeral=True)

class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="정보등록", description="내전 참여를 위한 정보를 등록하거나 수정합니다.")
    async def register_command(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PlayerInfoModal(self.bot))

    # cogs/registration.py 파일의 my_rank_command 함수

    @app_commands.command(name="내순서", description="현재 나의 내전 대기열 순서를 확인합니다.")
    async def my_rank_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            queue_response = self.bot.supabase.table('queue').select('player_id').order('created_at').execute()
            if not queue_response.data:
                await interaction.followup.send("현재 대기열이 비어있습니다.", ephemeral=True)
                return
            
            all_player_ids = [player['player_id'] for player in queue_response.data]
        
            if interaction.user.id in all_player_ids:
                rank = all_player_ids.index(interaction.user.id) + 1
            
                # [수정] 10순위 이내인지, 대기열인지 구분하여 응답
                if rank <= 10:
                    await interaction.followup.send(f"회원님은 현재 **다음 내전 참여 멤버({rank}순위)**입니다!", ephemeral=True)
                else:
                    wait_rank = rank - 10
                    await interaction.followup.send(f"현재 회원님의 실제 대기 순서는 **{wait_rank}번**입니다. (전체 순위: {rank}번)", ephemeral=True)
            else:
                await interaction.followup.send("회원님은 현재 대기열에 없습니다. '내전 참여' 버튼을 눌러주세요.", ephemeral=True)
        except Exception as e:
            print(f"내 순서 확인 오류: {e}")
            await interaction.followup.send("❌ 순서 확인 중 오류가 발생했습니다.", ephemeral=True)
    
    @app_commands.command(name="포인트", description="나의 현재 내전 포인트와 전체 랭킹을 확인합니다.")
    async def my_points_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = interaction.user.id
        
            # 1. [수정] DB에서 모든 유저의 포인트 정보를 랭킹 순으로 가져옵니다.
            all_players_res = self.bot.supabase.table('players').select('id, points').order('points', desc=True).execute()
        
            if not all_players_res.data:
                await interaction.followup.send("아직 랭킹 데이터가 없습니다.", ephemeral=True)
                return

            all_players = all_players_res.data
        
            # 2. [신규] 내 순위와 포인트를 찾습니다.
            my_rank = -1
            my_points = 0
        
            for idx, player in enumerate(all_players):
                if player['id'] == user_id:
                    my_rank = idx + 1
                    my_points = player.get('points', 0)
                    break
        
            # 3. [수정] 결과에 따라 다른 메시지를 보냅니다.
            if my_rank != -1:
                await interaction.followup.send(
                    f"현재 {interaction.user.mention} 님의 내전 포인트는 **{my_points}점** 입니다. (전체 랭킹: **{my_rank}등**)",
                    ephemeral=True
                )
            else:
                # 랭킹에 없다는 것은 정보 등록을 안 했거나 포인트가 0점인 경우
                await interaction.followup.send("아직 `/정보등록`을 하지 않았거나 내전 참여 기록이 없습니다.", ephemeral=True)

        except Exception as e:
            print(f"포인트 확인 오류: {e}")
            await interaction.followup.send("❌ 포인트 확인 중 오류가 발생했습니다.", ephemeral=True)
    
    @app_commands.command(name="랭킹", description="서버 내 내전 포인트 랭킹 TOP 10을 보여줍니다.")
    async def rank_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            # points 컬럼을 기준으로 내림차순 정렬하여 상위 10명을 가져옵니다.
            rankers_res = self.bot.supabase.table('players').select('id, points').order('points', desc=True).limit(10).execute()
        
            if not rankers_res.data:
                await interaction.followup.send("아직 랭킹 데이터가 없습니다."); return

            embed = discord.Embed(title="🏆 내전 포인트 랭킹", description="서버 내 포인트 랭킹 TOP 10입니다.", color=discord.Color.blue())
        
            rank_list = []
            for idx, ranker in enumerate(rankers_res.data):
                try:
                    user = await self.bot.fetch_user(ranker['id'])
                    mention = user.mention
                except discord.NotFound:
                    mention = f"ID: {ranker['id']} (알 수 없음)"
            
                points = ranker.get('points', 0)
                rank_list.append(f"`{idx + 1:2d}` {mention} - **{points}점**")
        
            embed.add_field(name="TOP 10", value="\n".join(rank_list), inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"랭킹 확인 오류: {e}"); await interaction.followup.send("❌ 랭킹을 불러오는 중 오류가 발생했습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))