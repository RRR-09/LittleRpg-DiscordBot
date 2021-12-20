from argparse import ArgumentParser
from json import load as load_json
from re import findall
from subprocess import Popen, check_output  # nosec
from time import sleep
from typing import Dict


def launch(config: Dict):
    bash_cmd = f'cd "{config["directory"]}";{config["launch_command"]}'
    screen_cmd = f'screen -A -m -d -S {config["process_name"]} bash -c "{bash_cmd}"'
    Popen(screen_cmd)


def check(config: Dict) -> bool:
    screens_list = check_output(["screen", "-list"]).decode().lower()  # nosec
    running_processes = findall(r"[0-9]*\.(.*?)\t", screens_list)

    if config["process_name"] not in running_processes:
        return False
    return True


def main_loop(bot_config: Dict):
    while True:
        bot_active = check(bot_config)
        if not bot_active:
            launch(bot_config)
        sleep(1)


def main_init():
    parser = ArgumentParser(description="Discord bot arguments.")
    parser.add_argument(
        "--config", help="Filepath for the config JSON file", default="config.json"
    )
    args = parser.parse_args()
    config_file_name = str(args.config)
    with open(config_file_name, "r", encoding="utf-8") as config_file:
        loaded_config = load_json(config_file)
    config = loaded_config["watchdog_config"]
    config["bot_vars"]["process_name"] = (
        config["bot_vars"]["process_name"].replace(" ", "").lower()
    )
    config["watchdog_vars"]["process_name"] = (
        config["watchdog_vars"]["process_name"].replace(" ", "").lower()
    )

    watchdog_active = check(config["watchdog_vars"])
    if not watchdog_active:  # Check if we're running in a screen or not, easy launch
        launch(config["watchdog_vars"])
        exit()

    main_loop(config["bot_vars"])


if __name__ == "__main__":
    main_init()