import os
from traceback import format_exc

import discord
from dotenv import load_dotenv

import utils
from utils import BotClass

client_intents = discord.Intents(messages=True, guilds=True, members=True)
global bot
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


async def player_count():
    # TODO: player count
    bot.server_status = "0/0 players"
    await bot.client.change_presence(
        activity=discord.Game(name=bot.server_status, type=0)
    )


async def config():
    bot.guild = bot.client.get_guild(bot.discord_guild_id)

    # Instantiate channel objects
    bot.channels = {}
    for channel_name in bot.channel_ids:
        channel_id = bot.channel_ids[channel_name]
        bot.channels[channel_name] = bot.guild.get_channel(channel_id)

    # Instantiate role objects
    bot.roles = {}
    for role_name in bot.role_ids:
        role_id = bot.role_ids[role_name]
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
    await player_count()


def main():
    global bot
    bot.ready = False
    utils.do_log("Loading Config")

    bot = utils.load_config_to_bot(bot)  # Load a json to the bot class
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
