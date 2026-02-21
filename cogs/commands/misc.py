import discord
import yaml
import time
from discord import app_commands
from discord.ext import commands

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]

class MiscUtilsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Shows's you the bot's ping!")
    async def ping(self, interaction: discord.Interaction) -> None:
        start = time.perf_counter()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end = time.perf_counter()
        duration = (end - start) * 1000
        await interaction.edit_original_response(content=f"Pong! {duration:.2f}ms")

async def setup(bot: commands.Bot):
    await bot.add_cog(MiscUtilsCog(bot), guilds=[discord.Object(id=guild_id)])