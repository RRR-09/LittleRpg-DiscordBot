import discord
from discord.ext import commands, tasks

from utils import BotClass


class MinimumRole(commands.Cog):
    def __init__(self, bot: BotClass):
        self.bot = bot
        minimum_role_name = bot.CFG.get("minimum_role_name", None)
        if minimum_role_name is None:
            print("['minimum_role_to_have' not set, disabling minimum role subroutine]")
            return

        self.minimum_role = bot.roles.get(minimum_role_name, None)
        if self.minimum_role is None:
            print(
                f"['{self.minimum_role_name}' not a preset role, disabling minimum role subroutine]"
            )
            return
        log_channel_name = bot.CFG.get("admin_log_channel_name", "")
        self.log_channel = bot.channels.get(log_channel_name, None)

        self.check_members_have_minimum_role.start()

    @tasks.loop(seconds=30)
    async def check_members_have_minimum_role(self):
        async for member in self.bot.guild.fetch_members(limit=None):
            if len(member.roles) >= 2:  # Ignore users with 2 roles or more, likely fine
                continue

            if self.log_channel is not None:  # Log that someone was missing a role
                await self.log_channel.send(
                    f"Warning: {member.mention} missing Guest role. Adding."
                )

            await member.add_roles(self.minimum_role)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if self.minimum_role.id not in [role.id for role in member.roles]:
            await member.add_roles(self.minimum_role)