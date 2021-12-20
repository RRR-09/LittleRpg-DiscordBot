import argparse
import logging
import os
from traceback import format_exc

import discord
from dotenv import load_dotenv

import utils


class BotClass:
    def __init__(self, intents: discord.Intents):
        self.client = discord.Client(intents=intents)
        self.logger = logging.getLogger("discord")
        self.logger.setLevel(logging.ERROR)
        self.handler = logging.FileHandler(
            filename="discord.log", encoding="utf-8", mode="w"
        )
        self.handler.setFormatter(
            logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
        )
        self.logger.addHandler(self.handler)
        utils.do_log("Initialized Discord Client")


client_intents = discord.Intents(messages=True, guilds=True, members=True)
bot = BotClass(client_intents)


@bot.client.event
async def on_error(event, args="", kwargs=""):
    error = format_exc()
    await utils.log_error("[Uncaught Error] " + error)


@bot.client.event
async def on_message(message):
    if not bot.ready:  # Handle race condition
        return

    # Basic non-overridable shutdown command
    if (
        message.author.id == bot.discord_bot_owner_id
        and message.content.lower().startswith("/off")
    ):
        try:
            await message.delete()
        finally:
            await bot.client.close()
            await bot.client.logout()
            return

    # TODO: message functions
    message_cleaned = message
    message_cleaned.content = message_cleaned.content.replace(
        "@everyone", "@ everyone"
    ).replace("@here", "@ here")


async def config():
    bot.guild = bot.client.get_guild(bot.discord_guild_id)

    # Instantiate channel objects
    bot.channels = []
    for channel_name in bot.channel_ids:
        channel_id = bot.channels[channel_name]
        bot.channels[channel_name] = bot.guild.get_channel(channel_id)

    # Instantiate role objects
    bot.roles = []
    for role_name in bot.role_ids:
        role_id = bot.roles[role_name]
        bot.roles[role_name] = bot.guild.get_role(role_id)

    bot.server_status = "Querying server..."


@bot.client.event
async def on_ready():
    try:
        utils.do_log(f"Bot name: {bot.client.user.name}")
        utils.do_log(f"Bot ID: {bot.client.user.id}")
        await bot.client.change_presence(
            activity=discord.Game(name="Starting bot...", type=0)
        )
        await config()

        await bot.client.change_presence(
            activity=discord.Game(name=bot.server_status, type=0)
        )

        utils.do_log("Ready\n\n")
        bot.ready = True
    except Exception:
        await utils.log_error(
            f"\n\n\nCRITICAL ERROR: FAILURE TO INITIALIZE{format_exc()}"
        )
        await bot.client.close()
        await bot.client.logout()
        raise Exception("CRITICAL ERROR: FAILURE TO INITIALIZE")


def load_config_to_bot():
    parser = argparse.ArgumentParser(description="Discord bot arguments.")
    parser.add_argument(
        "--config", help="Filepath for the config JSON file", default="config.json"
    )
    args = parser.parse_args()
    try:
        with open(args.config, "r", encoding="utf-8") as config_file:
            loaded_config = utils.json_load_eval(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"'{args.config}' not found.")
    for config_key in loaded_config:
        loaded_val = loaded_config[config_key]
        setattr(bot, config_key, loaded_val)
        utils.do_log(
            f"Loaded config setting \n'{config_key}' ({type(loaded_val).__name__})\n{loaded_val} "
        )


def main():
    bot.ready = False
    utils.do_log("Loading Config")

    load_config_to_bot()  # Load a json to the bot class
    load_dotenv(verbose=True)

    # Merge any env vars with config vars, and make variables easily accessible
    utils.do_log(f"Discord token: {utils.censor_text(os.getenv('DISCORD_TOKEN'))}")

    # DiscordPy tasks
    utils.do_log("Loaded Config")
    utils.do_log("Logging in")
    bot.client.run(os.getenv("DISCORD_TOKEN"))
    utils.do_log("Logging out")


if __name__ == "__main__":
    main()
