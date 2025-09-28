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

async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))