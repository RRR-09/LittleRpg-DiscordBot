from asyncio import create_task
from typing import Dict, List, Union

import discord
from discord.ext import commands

from utils import BotClass


class InviteCheck(commands.Cog):
    def __init__(self, bot: BotClass):
        self.bot = bot

        self.welcome_channel = self.bot.channels.get("welcome", None)
        if self.welcome_channel is None:
            print("['welcome' channel not set, disabling invite check subroutine]")
            return

        self.custom_invite_format = bot.CFG.get(
            "custom_invite_format", "> {member_name} has joined from {invite_name}"
        )
        self.custom_invite_messages = bot.CFG.get("custom_invite_messages", {})
        create_task(self.update_invites())

    async def update_invites(self):
        self.invites = (await self.bot.guild.invites())[:]
        self.invite_map = await self.map_invites(self.invites)

    async def map_invites(self, invites: List[discord.Invite]):
        invite_map: Dict[str, Dict] = {}
        for invite in invites:
            invite_map[invite.code] = {"uses": invite.uses, "inviter": invite.inviter}
        return invite_map.copy()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        changed_invites: List[discord.Invite] = await self.bot.guild.invites()

        invite_message = self.custom_invite_format.format(
            member_name=member.display_name, invite_name="{invite_name}"
        )
        for invite in changed_invites:
            old_invite: Union[Dict, None] = self.invite_map.get(invite.code)
            if old_invite is None:
                invite_message = invite_message.format(
                    invite_name=invite.inviter.display_name
                )
                break
            if invite.uses <= old_invite["uses"]:
                continue
            custom_msg = self.custom_invite_messages.get(invite.code)
            if custom_msg is None:
                invite_message = invite_message.format(
                    invite_name=f"{invite.inviter.display_name}'s invite"
                )
            else:
                invite_message = invite_message.format(invite_name=custom_msg)
            break

        self.invites = changed_invites[:]
        self.invite_map = await self.map_invites(self.invites)

        await self.welcome_channel.send(invite_message)
