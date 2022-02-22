import json
from datetime import datetime
from pathlib import Path
from time import time
from traceback import format_exc
from typing import Any, Dict, List, Union

import discord
from discord.ext import commands, tasks

from utils import BotClass, do_log, get_est_time, json_load_eval, log_error


class Store(commands.Cog):
    def __init__(self, bot: BotClass):
        self.bot = bot
        self.backend_channel = bot.channels.get("store_backend", None)
        if self.backend_channel is None:
            log_error("['store_backend' channel not set, disabling store integration]")
            return

        self.transactions_channel = bot.channels.get("store_log", None)
        if self.transactions_channel is None:
            log_error("['store_log' channel not set, disabling store integration]")
            return

        self.error_log_channel = bot.channels.get("admin", None)
        if self.transactions_channel is None:
            log_error("['admin' channel not set, disabling store integration]")
            return

        data_file_name = "store_temporary_purchases.json"
        self.temp_purchases_data_folder_path = Path.cwd() / "data"
        self.temp_purchases_data_file_path = (
            self.temp_purchases_data_folder_path / data_file_name
        )

        # Load the datafile
        self.temp_purchases = {}
        try:
            with open(self.temp_purchases_data_file_path, "r") as json_file:
                self.temp_purchases = json_load_eval(json_file)
        except FileNotFoundError:
            Path(self.temp_purchases_data_folder_path).mkdir(exist_ok=True)
            with open(self.temp_purchases_data_file_path, "w") as json_file:
                json.dump(self.temp_purchases, json_file, indent=4)

        self.rcon_function = self.bot.client.get_cog(
            "MinecraftIntegration"
        ).rcon_command

        is_rcon_functional = self.rcon_function(only_auth=True)
        if not (is_rcon_functional):
            log_error(
                "[Could not establish RCON connection, disabling store integration]"
            )
            return

        self.discord_to_minecraft = self.bot.client.get_cog(
            "MinecraftIntegration"
        ).discord_to_minecraft

        self.check_member_has_minimum_role = self.bot.client.get_cog(
            "MinimumRole"
        ).check_member_has_minimum_role

        self.remove_temp_roles.start()

    async def log_transaction(self, transaction_obj: Dict):
        buy_time = get_est_time()
        user_name = transaction_obj.get("user_name")
        item_name = transaction_obj.get("item", {}).get("friendly_name")
        amount = f"${transaction_obj.get('gross')} {transaction_obj.get('currency')}"
        log_message = (
            f"__[{buy_time}]__\n``{user_name}`` bought ``{item_name}``\n{amount}"
        )
        await self.transactions_channel.send(log_message)

        path = Path.cwd() / "data" / "monthly_progress"
        current_goal_month = f"{datetime.now().strftime('%Y-%m')}.dat"
        current_income = 0.0

        try:
            with open(path / current_goal_month, "r") as data_file:
                current_income = float(data_file.read())

            current_income += transaction_obj.get("gross", 0)

            with open(path / current_goal_month, "w") as data_file:
                data_file.write(str(current_income))

        except FileNotFoundError:
            current_income += transaction_obj.get("gross", 0)
            Path(path).mkdir(exist_ok=True)
            with open(path / current_goal_month, "w") as data_file:
                data_file.write(str(current_income))

    async def give_ingame_items(self, transaction_obj: Dict):
        command_templates = transaction_obj.get("item", {}).get("commands")
        if command_templates is None:
            return

        user_name = transaction_obj.get("user_name")
        commands_to_run = [cmd.format(username=user_name) for cmd in command_templates]

        item_name = transaction_obj.get("item", {}).get("friendly_name")
        raw_text_obj: List[Dict[str, Any]] = [
            {"text": "[LittleRpg Store] ", "color": "green"},
            {"text": user_name, "color": "white", "bold": "true"},
            {"text": " has purchased ", "color": "white"},
            {"text": item_name, "color": "white", "bold": "true"},
            {"text": "!", "color": "white"},
        ]
        tellraw_command = f"tellraw @a {json.dumps(raw_text_obj)}"
        commands_to_run.append(tellraw_command)

        self.rcon_function(cmds=commands_to_run)

    def log_temp_roles(
        self, discord_id: int, temp_roles: List[Dict[str, Union[int, float]]]
    ):
        entry = self.temp_purchases.get(discord_id, [])
        entry = entry + temp_roles
        self.temp_purchases[discord_id] = entry

        with open(self.temp_purchases_data_file_path, "w") as json_file:
            json.dump(self.temp_purchases, json_file, indent=4)

    async def give_discord_roles(self, transaction_obj: Dict):
        roles: List[Dict] = transaction_obj.get("item", {}).get("discord_roles", None)
        if roles is None:
            return

        user_name = transaction_obj.get("user_name")
        user_discord_id = None
        for discord_id, profile in self.discord_to_minecraft.items():
            # Default to different datatype to ensure no false matches (None, "ERROR", "N/A")
            if profile.get("minecraft_name", -1) == user_name:
                user_discord_id = discord_id
                break
        if user_discord_id is None:
            await self.error_log_channel.send(
                f"Could not find {user_name}'s discord, but they bought something with a role!"
            )
            return
        user_discord = self.bot.guild.get_member(user_discord_id)
        if user_discord is None:
            await self.error_log_channel.send(
                f"{user_name} isn't in the discord anymore, but they bought something with a role!"
            )
            return

        roles_to_add = []
        roles_to_remove = []
        temp_roles = []
        current_time = time()
        for role in roles:
            role_name = role.get("name", "role_name_not_found")
            role_instance = self.bot.roles.get(role_name)
            if role_instance is None:
                do_log(f"[Store] Could not find role {role_name}")
                continue

            if role is None:
                continue
            if role.get("add", True):
                roles_to_add.append(role_instance)
                # TODO: Daily role check to remove temp roles
                days = role.get("duration_days", -1)
                if days != -1:
                    temp_roles.append(
                        {
                            "role_id": role_instance.id,
                            "expiry_timestamp": round(
                                current_time + (days * 24 * 60 * 60)
                            ),
                        }
                    )
                    await self.error_log_channel.send(
                        f"{user_name} ({user_discord.name}#{user_discord.discriminator}) has purchased a temporary "
                        f"role ({role_instance.name} for {days} days).\nAutomatic role strip, or notification if "
                        "failed will occur, but keep an eye out regardless."
                    )

            else:
                roles_to_remove.append(role_instance)
        if temp_roles:
            self.log_temp_roles(user_discord.id, temp_roles)
        if roles_to_add:
            await user_discord.add_roles(*roles_to_add)
        if roles_to_remove:
            await user_discord.remove_roles(*roles_to_remove)

    @tasks.loop(seconds=60)
    async def remove_temp_roles(self):
        current_time = time()

        for discord_id in self.temp_purchases:
            discord_id = int(discord_id)
            try:
                member = self.bot.guild.get_member(discord_id)
            except Exception:
                do_log(
                    f"[remove_temp_roles] Member with discord id '{discord_id}' not found"
                )
                continue
            temp_roles = self.temp_purchases[discord_id]
            remaining_roles = []
            for role_entry in temp_roles:
                try:
                    expiry_timestamp = int(role_entry["expiry_timestamp"])
                except Exception:
                    log_error(
                        f"[Temp Role] Could not get expiry_timestamp for discord id '{discord_id}'\n"
                        f"{temp_roles}\n"
                    )
                    continue
                if expiry_timestamp > current_time:
                    remaining_roles.append(role_entry)
                    continue
                try:
                    role_id = int(role_entry["role_id"])
                    role_instance = self.bot.guild.get_role(role_id)
                    if role_instance is None:
                        raise Exception(
                            f"Could not find role on discord by id '{role_id}'"
                        )
                    if member is None:
                        raise Exception(
                            f"Could not find member on discord by id '{discord_id}'"
                        )
                    await member.remove_roles(
                        role_instance, reason="Temporary Purchased Role Expired"
                    )
                except Exception as e:
                    log_error(f"[remove_temp_roles]\n{format_exc()}\n")

                    await self.error_log_channel.send(
                        f"Could not remove temporary role from discord id '{discord_id}', check bot error logs\n`{e}`"
                    )
                    continue

                await self.error_log_channel.send(
                    f"Removed temporary role '{role_instance.name}' from discord member {member.mention}"
                )

            self.temp_purchases[discord_id] = remaining_roles
            await self.check_member_has_minimum_role(member, do_warn=False)

        with open(self.temp_purchases_data_file_path, "w") as json_file:
            json.dump(self.temp_purchases, json_file, indent=4)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != self.backend_channel.id:
            return

        transaction_obj = {}
        try:
            transaction_obj = json.loads(message.content)
        except Exception:
            log_error(f"[Store] Failed to make transaction into dict {message.content}")
            return

        await self.log_transaction(transaction_obj)
        await self.give_ingame_items(transaction_obj)
        await self.give_discord_roles(transaction_obj)
