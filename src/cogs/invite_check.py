from asyncio import create_task
from asyncio import sleep as async_sleep
from time import time
from typing import Any, Dict, List, Union

import discord
from discord.ext import commands

from utils import BotClass, do_log, log_error


class InviteCheck(commands.Cog):
    def __init__(self, bot: BotClass):
        self.bot = bot

        welcome_channel_name = self.bot.CFG.get("custom_invite_channel", "welcome")
        welcome_channel = self.bot.channels.get(welcome_channel_name, None)
        if welcome_channel is None:
            print("['welcome' channel not set, disabling invite check subroutine]")
            return
        self.welcome_channel = welcome_channel

        self.debug = self.bot.CFG.get("custom_invite_debug", False)

        self.attempts = self.bot.CFG.get("custom_invite_attempts", 3)

        self.custom_invite_format = bot.CFG.get(
            "custom_invite_format", "> {member_name} has joined from {invite_name}"
        )
        self.custom_invite_messages = bot.CFG.get("custom_invite_messages", {})
        self.latest_join_time = 0.0
        self.latest_single_use = 0.0
        self.latest_single_use_invite: Union[None, Dict[str, Any]] = None

        create_task(self.update_invites())

    async def update_invites(self):
        self.invites = (await self.bot.guild.invites())[:]
        self.invite_map = await self.map_invites(self.invites)

    async def map_invites(self, invites: List[discord.Invite]):
        invite_map: Dict[str, Dict] = {}
        for invite in invites:
            invite_map[invite.code] = {
                "uses": invite.uses,
                "inviter": invite.inviter,
                "max_uses": invite.max_uses,
            }
        return invite_map.copy()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Intercept a recently finished finite-use invite
        self.latest_join_time = time()
        await async_sleep(2)

        found_invite = False
        attempts = self.attempts
        invite_message = self.custom_invite_format.format(
            member_name=member.mention, invite_name="{invite_name}"
        )
        current_invites: List[discord.Invite] = await self.bot.guild.invites()
        if self.debug:
            do_log(f"Old Invite Map:\n{self.invite_map}\n")
            new_invite_map = await self.map_invites(current_invites)
            do_log(f"New Invite Map:\n{new_invite_map}\n")

        if (
            abs(self.latest_single_use - self.latest_join_time) < 4
            and self.latest_single_use_invite is not None
        ):
            found_invite = True
            attempts = 0
            inviter_mention = self.latest_single_use_invite["inviter"].mention

            invite_message = invite_message.format(
                invite_name=f"{inviter_mention}'s invite ({self.latest_single_use_invite['code']})"
            )

        for _ in range(attempts):
            for invite in current_invites:
                # Skip any invites that were not used
                if invite.uses is not None and invite.uses <= 0:
                    continue

                if invite.inviter is not None:
                    inviter_mention = invite.inviter.mention

                # If the invite wasn't logged, it was newly added (and used)
                old_invite: Union[Dict, None] = self.invite_map.get(invite.code)
                if old_invite is None:
                    invite_message = invite_message.format(
                        invite_name=f"{inviter_mention}'s invite ({invite.code})"
                    )
                    found_invite = True
                    break

                # If it was logged and it hasn't increased since our record of it, skip
                if invite.uses <= old_invite["uses"]:
                    continue

                # Show a custom message for any invites we know the source of and have a message for
                found_invite = True
                invite_name = f"{inviter_mention}'s invite ({invite.code})"
                custom_msg = self.custom_invite_messages.get(invite.code)
                if custom_msg is not None:
                    invite_name = custom_msg
                invite_message = invite_message.format(invite_name=invite_name)
                break

            if found_invite:
                break

        if not (found_invite):
            new_invite_map = await self.map_invites(current_invites)
            log_error(
                "[COULD NOT FIND INVITE USED]\n"
                f"Old Invite Map:\n{self.invite_map}\n\n"
                f"New Invite Map:\n{new_invite_map}\n\n"
            )
            invite_message = invite_message.format(invite_name="[ERROR]")

        self.invites = current_invites[:]
        self.invite_map = await self.map_invites(self.invites)

        await self.welcome_channel.send(invite_message)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        await self.update_invites()

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        mapped_invite = self.invite_map.get(invite.code)
        if mapped_invite is not None:
            single_use = mapped_invite["max_uses"] != 0
            if (
                single_use
                and mapped_invite["uses"] is not None
                and mapped_invite["max_uses"] is not None
            ):
                uses_left = mapped_invite["max_uses"] - mapped_invite["uses"]
                if uses_left <= 1:
                    self.latest_single_use = time()
                    mapped_invite["code"] = invite.code
                    self.latest_single_use_invite = mapped_invite
        else:
            await self.update_invites()
