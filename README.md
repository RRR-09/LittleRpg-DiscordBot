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
