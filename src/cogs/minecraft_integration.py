import json
from ftplib import FTP  # nosec
from ftplib import error_perm  # nosec
from os import getenv
from pathlib import Path
from re import sub as re_sub
from traceback import format_exc
from typing import Any, Dict, List

import discord
from discord.ext import commands, tasks
from mctools import RCONClient
from parse import compile as parser_compile
from yaml import safe_load as yaml_safe_load

from utils import BotClass, json_load_eval, log_error


class MinecraftIntegration(commands.Cog):
    def __init__(self, bot: BotClass):
        self.bot = bot
        init_functions = [self.init_discordsrv, self.init_ingame_chat]
        self.enabled = True
        for function in init_functions:
            if not function():
                self.enabled = False
                print("[Failure in initializing Minecraft integration, disabling.]")
                return
        self.nickname_sync.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.enabled:
            return
        await self.message_ingame_channel(message)
        await self.message_discordsrv_dm(message)

    def init_discordsrv(self) -> bool:
        self.discord_to_minecraft = {}
        self.nickname_sync_skip = self.bot.CFG.get("nickname_sync_skip_discord_ids", [])

        data_file_name = "profile_links.json"
        data_folder_path = Path.cwd() / "data"
        self.data_file_path = data_folder_path / data_file_name

        discordsrv_message = self.bot.CFG.get("discordsrv_message", None)
        if discordsrv_message is None:
            print("['discordsrv_message' not defined in config]")
            return False
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
        return True

    async def message_discordsrv_dm(self, message: discord.Message):
        if message.guild is not None or message.author.id != self.bot.client.user.id:
            return  # Filter messages that aren't DMs or from the bot

        parsed = self.message_parser.parse(message.content)
        if parsed is None or ("name" not in parsed or "uuid" not in parsed):
            return  # Filter messages that don't give us what we need

        minecraft_name, minecraft_uuid = str(parsed["name"]), str(parsed["uuid"])
        discord_user = message.channel.recipient
        discord_name = f"{discord_user.name}#{discord_user.discriminator}"

        existing = False
        for user in self.discord_to_minecraft.values():
            if minecraft_uuid == user["minecraft_uuid"]:
                existing = True
                break

        self.discord_to_minecraft[discord_user.id] = {
            "minecraft_name": minecraft_name,
            "minecraft_uuid": minecraft_uuid,
            "discord_name": discord_name,  # Not kept up-to-date, just human-readable indicator
        }
        with open(self.data_file_path, "w") as json_file:
            json.dump(self.discord_to_minecraft, json_file, indent=4)

        if not existing:
            self.rcon_command(f"crazycrate give physical Boost 1 {minecraft_name}")
            await discord_user.send(
                "For verifying, you have been given 1 Boost key!\n"
                "If you do not see it, please run the ``/keys`` command to see if you have a virtual key.\n"
                "If you did not receive a key, please contact staff."
            )

        try:
            discord_member = self.bot.guild.get_member(discord_user.id)
            await discord_member.add_roles(self.bot.roles["player"])
            await discord_member.remove_roles(self.bot.roles["guest"])
        except Exception:
            await log_error(format_exc())

    def init_ingame_chat(self) -> bool:
        self.censor_function = self.bot.client.get_cog("Censor").should_censor_message

        self.ftp_host = getenv("MINECRAFT_FTP_HOST", "")
        self.ftp_username = getenv("MINECRAFT_FTP_USERNAME", "")
        self.ftp_password = getenv("MINECRAFT_FTP_PASSWORD", "")
        if "" in [self.ftp_host, self.ftp_username, self.ftp_password]:
            print("[One or more FTP .env variables are empty]")
            return False

        self.rcon_host = getenv("MINECRAFT_RCON_HOST", "")
        self.rcon_password = getenv("MINECRAFT_RCON_PASSWORD", "")
        self.rcon_port = getenv("MINECRAFT_RCON_PORT", "")
        if "" in [self.rcon_host, self.rcon_password, self.rcon_port]:
            print("[One or more RCON .env variables are empty]")
            return False

        ingame_channel_name = self.bot.CFG.get("ingame_chat_channel_name", None)
        if ingame_channel_name is None:
            print("['ingame_chat_channel_name' not defined in config]")
            return False

        self.ingame_channel = self.bot.channels.get(ingame_channel_name, None)
        if self.ingame_channel is None:
            print("f['{self.ingame_chat_channel_name}' not a valid channel]")
            return False

        return True

    def rcon_command(self, cmd=None, cmds=None, only_auth=False):
        rcon = RCONClient(self.rcon_host, port=self.rcon_port)
        try:
            rcon.login(self.rcon_password)
            if not rcon.is_authenticated():
                raise ConnectionRefusedError  # Raises this anyway in severe failure
        except ConnectionRefusedError:
            print("[RCON failed to authenticate]")
            try:
                rcon.stop()
            except Exception:  # Not sure what exception would happen here
                return False
            return False
        if not only_auth:
            commands_to_execute = []
            if cmds is None and cmd is not None:
                commands_to_execute.append(cmd)
            else:
                commands_to_execute = cmds[:]

            for cmd in commands_to_execute:
                response = rcon.command(cmd, length_check=False)
                print(response)

            try:
                rcon.stop()
            except Exception:  # Not sure what exception would happen here
                return False
        return True

    async def message_ingame_channel(self, message: discord.Message):
        if message.channel.id != self.ingame_channel.id or message.author.bot:
            return
        if await self.censor_function(message.clean_content):
            return

        embed = discord.Embed()
        embed.title = "Discord-to-Minecraft"
        clean_everyone_content = (
            message.clean_content if message.mention_everyone else message.content
        )
        embed.description = (
            f"**{message.author.display_name}:** {clean_everyone_content}"
        )
        # if not self.bot.minecraft_server_online:
        #     embed.set_footer(text="Server is not online!")
        #     await message.channel.send(embed=embed)
        #     return

        try:
            failed = False
            failed_msg = "Unknown Error!"
            if message.author.id in self.discord_to_minecraft:
                profile = self.discord_to_minecraft[message.author.id]
                user_uuid = profile["minecraft_uuid"]
                user_name = profile["minecraft_name"]
                embed.description = f"**{user_name}:** {clean_everyone_content}"
                essentials_profile = await self.get_essentials_profile(user_uuid)

                if essentials_profile["success"] is False:
                    raise Exception("Failure in 'get_essentials_profile' function")
                elif not essentials_profile["data"]:  # Empty/Falsey
                    failed = True
                    failed_msg = f"Could not find Essentials profile for Minecraft ID `{user_uuid}` ({user_name})!"
                else:
                    display_name = user_name
                    clean_display_name = user_name
                    if "nickname" in essentials_profile["data"]:
                        display_name = essentials_profile["data"]["nickname"]
                        clean_display_name = re_sub(r"(§[a-zA-Z0-9])", "", display_name)
                    embed.description = (
                        f"[Discord] {clean_display_name}: {clean_everyone_content}"
                    )

                    raw_text_obj: List[Dict[str, Any]] = [
                        {"text": "[", "color": "white"},
                        {"text": "Discord", "color": "blue"},
                        {"text": "] ", "color": "white"},
                    ]
                    if clean_display_name == display_name:
                        raw_text_obj.append({"text": display_name, "color": "gray"})
                    else:
                        formatted_name = self.tellraw_formatter(display_name)
                        for obj in formatted_name:
                            raw_text_obj.append(obj)
                    raw_text_obj.append({"text": " >> ", "bold": True, "color": "gray"})
                    raw_text_obj.append(
                        {"text": message.clean_content, "color": "white"}
                    )

                    tellraw_str = json.dumps(raw_text_obj)
                    self.rcon_command(f"tellraw @a {tellraw_str}")

                    await message.channel.send(embed=embed)
                    await message.delete()
            else:
                failed = True
                failed_msg = "Could not find your username!\nHave you linked your discord on the Minecraft server?"
            if failed:
                await message.add_reaction("🕵️")
                await message.add_reaction("❌")
                try:
                    await message.author.send(failed_msg)
                except Exception:
                    await message.channel.send(failed_msg)
                await message.delete()
        except Exception:
            error = format_exc()
            if "mcipc.rcon.errors.NoPlayerFound" not in error:
                await log_error(f"[Discord-To-Minecraft]\n{error}")
                await message.add_reaction("📡")
                await message.add_reaction("❌")
                embed.set_footer(text="Failed to send: Unknown error.")
                await message.channel.send(embed=embed)
                await message.delete()
            else:
                embed.set_footer(
                    text="Note: No players online when this message was sent."
                )
                await message.channel.send(embed=embed)
                await message.delete()

    async def get_essentials_profile(self, uuid) -> Dict[str, Any]:
        try:
            # No control over host, have to use ftp even if insecure
            with FTP(
                self.ftp_host, self.ftp_username, self.ftp_password
            ) as ftp:  # nosec
                ftp.cwd("/plugins/Essentials/userdata")
                yml_data_list: List[str] = []
                try:
                    ftp.retrlines(f"RETR {uuid}.yml", yml_data_list.append)
                except error_perm:
                    return {"success": True, "data": {}}
                yml_data_str = "\n".join(yml_data_list)
                return {"success": True, "data": yaml_safe_load(yml_data_str)}
        except Exception:
            await log_error("[GetEssentials Error] " + format_exc())
            return {"success": False, "data": {}}

    def tellraw_formatter(self, message):
        message_obj = []
        bold = False
        strikethrough = False
        underline = False
        italic = False
        colors = {
            "0": "black",
            "1": "dark_blue",
            "2": "dark_green",
            "3": "dark_aqua",
            "4": "dark_red",
            "5": "dark_purple",
            "6": "gold",
            "7": "gray",
            "8": "dark_gray",
            "9": "blue",
            "a": "green",
            "b": "aqua",
            "c": "red",
            "d": "light_purple",
            "e": "yellow",
            "f": "white",
        }
        formats = {
            "l": "bold",
            "m": "strikethrough",
            "n": "underline",
            "o": "italic",
            "r": "reset",
        }
        tmp_text = ""
        tmp_message_object = {}
        primed = False

        def get_format(bold, strikethrough, underline, italic):
            obj = {}
            if bold:
                obj["bold"] = True
            if strikethrough:
                obj["strikethrough"] = True
            if underline:
                obj["underline"] = True
            if italic:
                obj["italic"] = True
            return obj

        for character in message:
            if character == "§":
                primed = True
                continue
            elif primed:
                primed = False
                if character in colors:
                    if len(tmp_text) > 0:
                        tmp_message_object["text"] = tmp_text
                        message_obj.append(tmp_message_object)
                    tmp_text = ""
                    tmp_message_object = get_format(
                        bold, strikethrough, underline, italic
                    )
                    tmp_message_object["color"] = colors[character]
                    continue
                elif character not in formats:
                    continue

                if len(tmp_text) > 0:
                    tmp_message_object["text"] = tmp_text
                    message_obj.append(tmp_message_object)
                tmp_text = ""

                msg_format = formats[character]
                if msg_format == "bold":
                    bold = True
                elif msg_format == "strikethrough":
                    strikethrough = True
                elif msg_format == "underline":
                    underline = True
                elif msg_format == "italic":
                    italic = True
                elif msg_format == "reset":
                    bold = False
                    strikethrough = False
                    underline = False
                    italic = False
                    if "color" in tmp_message_object:
                        del tmp_message_object["color"]
                tmp_message_object = get_format(bold, strikethrough, underline, italic)
            else:
                tmp_text += character

        if len(tmp_text) > 0:
            tmp_message_object["text"] = tmp_text
            message_obj.append(tmp_message_object)

        return message_obj

    @tasks.loop(seconds=300)
    async def nickname_sync(self):
        found = 0
        needed_change = 0
        changed = 0
        for discord_id in self.discord_to_minecraft:
            profile = self.discord_to_minecraft[discord_id]
            member = self.bot.guild.get_member(discord_id)
            if member is None:
                print(f"[NameSync] User not in discord\n{profile}")
                continue
            found += 1

            if discord_id in self.nickname_sync_skip:
                continue

            final_name = profile["minecraft_name"]

            essentials_profile = await self.get_essentials_profile(
                profile["minecraft_uuid"]
            )

            if essentials_profile["success"] is False:
                log_error(
                    f"Failure in 'get_essentials_profile' function for nickname_sync\n{profile}"
                )
            elif (
                essentials_profile["data"] and "nickname" in essentials_profile["data"]
            ):
                final_name = re_sub(
                    r"(§[a-zA-Z0-9])", "", essentials_profile["data"]["nickname"]
                )

            if member.display_name.lower() != final_name.lower():
                needed_change += 1
                try:
                    await member.edit(nick=final_name)
                    changed += 1
                except Exception:
                    error = format_exc()
                    await log_error(
                        f"[coroutine_nickname_sync] {member.display_name} / {profile['minecraft_username']}\n{error}"
                    )
        print(
            f"[NameSync] {found}/{len(self.discord_to_minecraft)} found, {changed}/{needed_change} changed"
        )
