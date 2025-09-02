# bot.py 

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import create_client, Client

# --- 1. 환경 변수 로드 및 클라이언트 초기화 ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class ValorantBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="/", intents=intents)
        
        # Supabase 클라이언트를 봇 인스턴스의 속성으로 추가
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    async def setup_hook(self):
        # cogs 폴더에 있는 .py 파일들을 모두 불러옵니다.
        print("--- Cogs Loading ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ {filename[:-3]}")
                except Exception as e:
                    print(f"❌ {filename[:-3]}: {e}")
        print("--------------------")

        # 슬래시 커맨드를 서버에 동기화합니다.
        try:
            synced = await self.tree.sync()
            print(f'{len(synced)}개의 슬래시 커맨드를 동기화했습니다.')
        except Exception as e:
            print(f'커맨드 동기화 중 오류 발생: {e}')

bot = ValorantBot()

# --- 2. 봇 실행 ---
try:
    bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure:
    print("❌ 디스코드 토큰이 잘못되었습니다. .env 파일을 확인해주세요.")
except Exception as e:
    print(f"❌ 봇 실행 중 알 수 없는 오류 발생: {e}")