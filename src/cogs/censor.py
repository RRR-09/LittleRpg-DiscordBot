import re
from typing import List

import discord
from discord.ext import commands

from utils import BotClass


class Censor(commands.Cog):
    def __init__(self, bot: BotClass):
        cfg = bot.CFG.get("censor", {})
        self.channels_without_censoring = cfg.get("channels_without_censoring", [])
        self.words_startswith = cfg.get("words_startswith", [])
        self.words_independent = cfg.get("words_independent", [])
        self.highest_censored_role_name = cfg.get("highest_censored_role_name", "")
        self.bots_no_warn_channel_names = cfg.get("bots_no_warn_channel_names", [])

        self.highest_censored_role = bot.roles.get(
            self.highest_censored_role_name, None
        )
        self.bots_no_warn_channel_ids = [
            bot.CFG["discord_channel_ids"].get(channel_name, -1)
            for channel_name in self.bots_no_warn_channel_names
        ]
        self.words_regex = re.compile(r"[\W_]+", re.UNICODE)
        self.uncensored_channels: List[int] = []
        self.bot = bot

        for channel in self.bot.guild.text_channels:
            do_not_censor = channel.id in self.channels_without_censoring

            if do_not_censor or self.is_mod_chat(channel):
                self.uncensored_channels.append(channel.id)

    def is_mod_chat(self, channel: discord.TextChannel) -> bool:
        not_everyone_can_see = False
        for overwrite in channel.overwrites_for(channel.guild.default_role):
            if overwrite is None:
                continue
            permission_name, permission_value = overwrite
            if permission_name == "read_messages":
                not_everyone_can_see = permission_value is False
                break

        if not_everyone_can_see:  # Include VIP-like chats
            highest_role_cant_see = False
            if self.highest_censored_role is not None:
                for overwrite in channel.overwrites_for(self.highest_censored_role):
                    if overwrite is None:
                        continue
                    permission_name, permission_value = overwrite
                    if permission_name == "read_messages":
                        highest_role_cant_see = permission_value is not True
                        break
            if highest_role_cant_see:
                return True
        return False

    async def should_censor_message(self, text):
        censor = False
        split_message = self.words_regex.sub("", text.lower()).split(" ")
        for censored_word in self.words_startswith:
            for word in split_message:
                if word.startswith(censored_word):
                    censor = True
        # Split by spaces
        if not censor and any(word in split_message for word in self.words_independent):
            censor = True
        return censor

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id in self.uncensored_channels:
            return
        if await self.should_censor_message(message.content):
            await message.delete()
            embed = discord.Embed()
            embed.title = f"Bad Language in #{message.channel.name}"
            embed.description = (
                f"{message.author.mention}, Please don't use bad language 😟\n"
                "Also, please don't attempt to bypass this chat filter or you will get in trouble."
            )

            if message.author.bot:
                if message.channel.id not in self.bots_no_warn_channel_ids:
                    embed.description = (
                        "Somehow, this bot sent bad language. Please tell a staff member if you identify "
                        "the cause. "
                    )
                    await message.channel.send(embed=embed)
            else:
                try:
                    message_content = message.content.replace("`", "\\`")
                    embed_with_message = embed
                    embed_with_message.description += (
                        f"\n** **\nYour message: ```{message_content}```"
                    )
                    await message.author.send(embed=embed_with_message)
                except Exception:
                    embed.title = "Bad Language"
                    await message.channel.send(embed=embed)
