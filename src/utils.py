import logging
from argparse import ArgumentParser
from datetime import datetime
from json import load as load_json
from math import floor
from typing import Any, Dict, List, TextIO, Tuple, Union

from discord import Guild as DiscordGuild
from discord import Intents as DiscordIntents
from discord import Member as DiscordMember
from discord import Message as DiscordMessage
from discord import Role as DiscordRole
from discord import TextChannel as DiscordChannel
from discord import User as DiscordUser
from discord import Webhook as DiscordWebhook
from discord.ext.commands import Bot as DiscordBot
from pytz import timezone


class BotClass:
    def __init__(self):
        intents = DiscordIntents.default()
        intents.members = True
        intents.guilds = True
        intents.messages = True

        self.client = DiscordBot(command_prefix="/", intents=intents)
        self.logger = logging.getLogger("discord")
        self.logger.setLevel(logging.ERROR)
        self.handler = logging.FileHandler(
            filename="discord.log", encoding="utf-8", mode="w"
        )
        self.handler.setFormatter(
            logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
        )
        self.logger.addHandler(self.handler)

        self.CFG: Dict[Any, Any] = {}
        self.guild = DiscordGuild
        self.channels: Dict[str, DiscordChannel] = {}
        self.roles: Dict[str, DiscordRole] = {}
        self.ready = False
        do_log("Initialized Discord Client")


def censor_text(text: str, leave_uncensored: int = 4) -> str:
    """
    Censors the second half (excluding the last 'leave_uncensored' number of letters) for the
    string argument 'text'
    """
    return (
        text[: int(len(text) / 2)]
        + str("*" * (int(len(text) / 2) - 4))
        + text[:leave_uncensored]
    )


def get_est_time(time_to_convert: datetime = None) -> str:
    """
    Gets the current time (or 'time_to_convert' arg, if provided) as datetime and converts it to a
    readable string
    """
    desired_timezone = timezone("America/Toronto")
    if time_to_convert is not None:
        # TODO: Take in a datetime and convert to EST
        do_log("GET_EST_TIME ERROR, PLEASE IMPLEMENT CONVERTER")
        return "ERROR"
    else:
        return datetime.now(desired_timezone).strftime("%Y-%b-%d %I:%M:%S %p EST")


def do_log(message: str):
    print(f"[{get_est_time()}] {message}")


def log_error(error: str):
    if "KeyboardInterrupt" in error:
        raise KeyboardInterrupt
    error_message = f"[{get_est_time()}]\n{error}"
    error_log_filename = "errors.log"
    try:
        with open(error_log_filename, "a") as error_log:
            error_log.write(error_message)
    except FileNotFoundError:
        with open(error_log_filename, "w") as error_log:
            error_message = f"[{get_est_time()}] WARNING: Failed to find existing error log. Writing to new.\n\n{error}"
            error_log.write(error_message)
    do_log(error_message)


def json_eval_object_pairs_hook(ordered_pairs: List[Tuple[Any, Any]]) -> Dict:
    """
    Additional hook for JSON loader to turn any strings into representative datatypes (bool, int,
    float) wherever possible.
    """
    special = {
        "true": True,
        "false": False,
        "null": None,
    }
    result = {}
    for key, value in ordered_pairs:
        if key in special:
            key = special[key]
        else:
            for numeric in int, float:
                try:
                    key = numeric(key)
                except ValueError:
                    continue
                else:
                    break
        result[key] = value
    return result


def json_load_eval(fp_obj: TextIO) -> Dict:
    """
    Loads a JSON file, evaluating any strings to possible variables.
    """
    return load_json(fp_obj, object_pairs_hook=json_eval_object_pairs_hook)


async def find_server_member(
    guild: DiscordGuild,
    message: DiscordMessage = None,
    discord_id: Union[int, str] = None,
) -> Union[DiscordMember, None]:
    """
    Given a search query (message arg) or a discord id, attempts to find the user as a Member
    object using the guild provided in arguments.
    """

    # TODO: Clean this function up
    message_copy = message
    if message_copy is None:
        message_copy = DiscordMessage
        message_copy.content = "_ " + str(discord_id)
        message_copy.guild = guild
    msg = message_copy.content.split(" ")
    if len(msg) > 1 and msg[1] == "":
        msg[1] = msg[2]
    if len(msg) == 1 and discord_id is None:
        user = message_copy.author
    elif msg[1].replace("<@", "").replace("!", "").replace(">", "").isdigit():
        msg = int(msg[1].replace("<@", "").replace("!", "").replace(">", ""))
        user = message_copy.guild.get_member(msg)
    else:
        msg = msg[1]
        user = message_copy.guild.get_member_named(msg)
        if user is None:
            member_obj = {}
            for member in message_copy.guild.members:
                nick = "" if member.display_name == member.name else member.display_name
                member_obj[member.id] = {
                    "nickname": nick,
                    "username": member.name,
                    "discriminator": member.discriminator,
                }

            # nickname case insensitive
            for id in member_obj:
                member = member_obj[id]
                if msg == member["nickname"].lower():
                    user = id
                    break
            if user is None:
                # username case insensitive
                for id in member_obj:
                    member = member_obj[id]
                    if msg == member["username"].lower():
                        user = id
                        break
                if user is None:
                    # nickname case insensitive startswith match
                    for id in member_obj:
                        member = member_obj[id]
                        if member["nickname"].lower().startswith(msg):
                            user = id
                            break
                    if user is None:
                        # username case insensitive startswith match
                        for id in member_obj:
                            member = member_obj[id]
                            if member["username"].lower().startswith(msg):
                                user = id
                                break
                        if user is None:
                            # nickname case insensitive loose match
                            for id in member_obj:
                                member = member_obj[id]
                                if msg in member["nickname"].lower():
                                    user = id
                                    break
                            if user is None:
                                # username case insensitive loose match
                                for id in member_obj:
                                    member = member_obj[id]
                                    if msg in member["username"].lower():
                                        user = id
                                        break
                                if user is None:
                                    return None
            user = message_copy.guild.get_member(user)
    return user


async def get_hook_in_server(
    message: DiscordMessage, hook_user: DiscordUser
) -> DiscordWebhook:
    hooks = await message.channel.webhooks()
    found_hook = None
    for h in hooks:
        if h.user.id == hook_user.id:
            found_hook = h
            break
    if found_hook is None:
        found_hook = await message.channel.create_webhook(name=hook_user.display_name)
    return found_hook


async def is_member_admin(
    member: Union[str, DiscordMember], guild: DiscordGuild
) -> bool:
    """
    Given a member ID or Member object, attempts to find if they have admin permissions or not in
    the specified Discord guild.
    """
    if isinstance(member, str):
        member_id = member
        member = guild.get_member(member)
        if member is None:
            log_error(f'[{get_est_time()}] ERROR: Could not find member "{member_id}".')
            return False
    try:
        if not member.guild_permissions.manage_guild:
            return False
    except Exception:
        return False
    return True


async def get_english_timestamp(time_var: Union[int, float]) -> str:
    """
    Takes in a time, in seconds, and converts it to a readable string representing
    elapsed or remaining time (i.e. "1 day, 2 hours, 3 minutes, 4 seconds")
    """
    original_time = time_var
    seconds_in_minute = 60
    seconds_in_hour = 60 * seconds_in_minute
    seconds_in_day = 24 * seconds_in_hour
    days = floor(time_var / seconds_in_day)
    time_var -= days * seconds_in_day
    hours = floor(time_var / seconds_in_hour)
    time_var -= hours * seconds_in_hour
    minutes = floor(time_var / seconds_in_minute)
    time_var -= minutes * seconds_in_minute
    seconds = round(time_var)
    if minutes == 0:
        return "{} second{}".format(seconds, "s" if seconds != 1 else "")
    if hours == 0:
        return "{} minute{}".format(minutes, "s" if minutes != 1 else "")
    hours_rounded = round(original_time / seconds_in_hour, 1)
    if days == 0:
        return "{} hour{}".format(hours_rounded, "s" if hours_rounded != 1 else "")
    return "{} day{}, {} hour{}".format(
        days, "s" if days != 1 else "", hours_rounded, "s" if hours_rounded != 1 else ""
    )


def load_config_to_bot(bot_instance: BotClass) -> BotClass:
    parser = ArgumentParser(description="Discord bot arguments.")
    parser.add_argument(
        "--config", help="Filepath for the config JSON file", default="config.json"
    )
    args = parser.parse_args()
    try:
        with open(args.config, "r", encoding="utf-8") as config_file:
            loaded_config = json_load_eval(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"'{args.config}' not found.")
    for config_key in loaded_config:
        loaded_val = loaded_config[config_key]
        bot_instance.CFG[config_key] = loaded_val
        do_log(
            f"Loaded config setting \n'{config_key}' ({type(loaded_val).__name__})\n{loaded_val} "
        )
    return bot_instance
