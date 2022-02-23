# About
A contracted Discord bot for a Minecraft Server.
## If slow to start/shutdown/restart:
There is a strange issue with discord.py and pynacl that leads it to hang in some cases. Running `poetry run pip install pynacl -I --no-binary pynacl` after the standard `poetry install` should fix any issues.

# Functions (and items to manually test):
## Basic Functions
1. Leave functionality 
    - Selects a random "leave" message and sends it to the configured channel when a Discord member leaves the guild
2. Censor swear words from people and bots, except for:
    - Channels the general public can't see
3. Invite logging
    - When someone joins, compares last known invite mapping to invite map after they joined, and sends a message indicating what invite was used and who's invite it was, or if its a pre-mapped invite from the config file it displays a custom message instead. (This feature also works for one-use invites)
4. Minimum role
    - At a regular interval as well as during certain events (user join, user role change) all members of the server are checked to see if they have a certain minimum role, in this case "Guest". If not, it applies it and warns staff so they can look into possible causes of why this user was missing a role.
5. Minecraft integration
    - Queries the server for online/offline status and player count, then puts it in the "now playing" status of the discord bot for ease of viewing
    - Hijacks DiscordSRV's linking system to provide augmented capability and a local database of what discord user maps to what in-game username
    - If a players account has been linked, they can type in a Discord channel and their message will appear in-game, including any customizations they have made on their in-game nickname (colors, formatting)
    - Syncs the Discord nicknames of anyone linked with their in-game nickname, for ease of identification
6. e-Commerce integration
    - Parses webhook data from completed purchases to log income
    - Hosts a small, hidden api endpoint that returns the current month's goal progress
    - Triggers a site-rebuild via POST when a transaction has been completed so it can requery the updated monthly progress (site is static, Gatsby)
    - Gives any Discord roles associated with the purchase to the customer
    - Uses an RCON connection from the "Minecraft integration" cog to give purchased items to the customer
    - A routine is always running in the background to see if anyone on the Discord server has an expired, purchased Discord role and removes it from them
