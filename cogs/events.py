# cogs/events.py

import discord
from discord.ext import commands

# '내전 참여' 버튼을 포함하는 View 클래스
class JoinView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot # supabase 클라이언트에 접근하기 위해 bot 객체를 저장

    @discord.ui.button(label="내전 대기열 참여", style=discord.ButtonStyle.success, custom_id="join_civil_war_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)
        try:
            # players 테이블에서 페널티 정보를 조회합니다.
            player_response = self.bot.supabase.table('players').select('strikes, penalty_ends_at').eq('id', user_id).single().execute()
        
            # 정보가 등록되지 않은 유저 먼저 확인합니다.
            if not player_response.data:
                await interaction.followup.send("⚠️ 먼저 `/정보등록`으로 정보를 등록해야 참여할 수 있습니다.", ephemeral=True)
                return
        
            player_data = player_response.data
        
            # 1. 스트라이크 개수 확인 (3개 이상이면 참여 불가)
            if player_data.get('strikes', 0) >= 3:
                await interaction.followup.send("❌ 스트라이크가 3개 이상 누적되어 참여가 제한됩니다. 운영자에게 문의하세요.", ephemeral=True)
                return

            # 2. 타임아웃 페널티 확인
            if player_data.get('penalty_ends_at'):
                from datetime import datetime, timezone
                penalty_end_time = datetime.fromisoformat(player_data['penalty_ends_at'])
                if penalty_end_time > datetime.now(timezone.utc):
                    end_time_timestamp = f"<t:{int(penalty_end_time.timestamp())}:R>"
                    await interaction.followup.send(f"❌ 타임아웃 페널티가 적용 중입니다. {end_time_timestamp}에 다시 시도해주세요.", ephemeral=True)
                    return

            # 이하 대기열 참여 로직은 기존과 동일합니다.
            in_queue = self.bot.supabase.table('queue').select('player_id').eq('player_id', user_id).execute().data
            if in_queue:
                await interaction.followup.send("이미 내전 대기열에 등록되어 있습니다.", ephemeral=True)
                return
        
            self.bot.supabase.table('queue').insert({'player_id': user_id}).execute()
            queue_response = self.bot.supabase.table('queue').select('player_id', count='exact').order('created_at').execute()
            total_in_queue = queue_response.count
            await interaction.followup.send(f"✅ 내전 대기열 참여 신청이 완료되었습니다! 현재 대기 순서는 {total_in_queue}번입니다.", ephemeral=True)
        except Exception as e:
            print(f"내전 참여 처리 오류: {e}")
            await interaction.followup.send("❌ 내전 참여 처리 중 오류가 발생했습니다.", ephemeral=True)

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'✅ {self.bot.user.name}(으)로 성공적으로 로그인했습니다!')
        print(f'봇 ID: {self.bot.user.id}')
        print('---------------------------------')
        # 봇이 재시작되어도 버튼이 계속 활성화되도록 View를 등록
        self.bot.add_view(JoinView(self.bot))

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))