import json
from pathlib import Path

import discord
from discord.ext import commands
from parse import compile as parser_compile

from utils import BotClass, json_load_eval


class MinecraftIntegration(commands.Cog):
    def __init__(self, bot: BotClass):
        self.bot = bot
        self.discord_to_minecraft = {}

        data_file_name = "profile_links.json"
        data_folder_path = Path.cwd() / "data"
        self.data_file_path = data_folder_path / data_file_name

        discordsrv_message = bot.CFG.get("discordsrv_message", None)
        if discordsrv_message is None:
            print(
                "[No 'discordsrv_message' value specified in config. Disabling Minecraft integration.]"
            )
            return
        self.message_parser = parser_compile(discordsrv_message)

        # Load the datafile
        try:
            with open(self.data_file_path, "r") as json_file:
                self.discord_to_minecraft = json_load_eval(json_file)
            print(
                f"[Loaded Minecraft integration datafile with {len(self.discord_to_minecraft)} users]"
            )
        except FileNotFoundError:
            Path(data_folder_path).mkdir(exist_ok=True)
            with open(self.data_file_path, "w") as json_file:
                json.dump(self.discord_to_minecraft, json_file, indent=4)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None or message.author.id != self.bot.client.user.id:
            return  # Filter messages that aren't DMs or from the bot

        parsed = self.message_parser.parse(message.content)
        if parsed is None or ("name" not in parsed or "uuid" not in parsed):
            return  # Filter messages that don't give us what we need

        minecraft_name, minecraft_uuid = str(parsed["name"]), str(parsed["uuid"])
        discord_user = message.channel.recipient
        discord_name = f"{discord_user.name}#{discord_user.discriminator}"
        self.discord_to_minecraft[discord_user.id] = {
            "minecraft_name": minecraft_name,
            "minecraft_uuid": minecraft_uuid,
            "discord_name": discord_name,  # Not kept up-to-date, just human-readable indicator
        }
        with open(self.data_file_path, "w") as json_file:
            json.dump(self.discord_to_minecraft, json_file, indent=4)
