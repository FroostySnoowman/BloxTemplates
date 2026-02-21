import discord
import yaml
from discord import app_commands
from discord.ext import commands

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
verified_role_id = data["Verification"]["VERIFIED_ROLE_ID"]

class VerificationButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji='✅', label='Verify', style=discord.ButtonStyle.gray, custom_id='verify_button')
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.client.get_guild(guild_id)
        if guild != interaction.guild:
            embed = discord.Embed(title="Error", description="This button is not for this server.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        role = guild.get_role(verified_role_id)
        if role is None:
            embed = discord.Embed(title="Error", description="Verified role not found. Please contact an administrator.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if role in interaction.user.roles:
            embed = discord.Embed(title="Already Verified", description="You already have the verified role.", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.user.add_roles(role)
        embed = discord.Embed(title="Verified", description="You have been verified and given the verified role!", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(VerificationButton())

    @app_commands.command(name="verification", description="Sends the verification embed")
    async def verification(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="Verification Required", description="Click the button below to verify yourself.", color=discord.Color.blue())
        await interaction.channel.send(embed=embed, view=VerificationButton())

        await interaction.response.send_message("Verification embed sent!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot), guilds=[discord.Object(id=guild_id)])