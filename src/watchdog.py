from argparse import ArgumentParser
from json import load as load_json
from re import findall
from subprocess import CalledProcessError, Popen, check_output  # nosec
from time import sleep
from typing import Dict

from utils import get_est_time


def launch(config: Dict):
    print(f"[{get_est_time()}] Launching {config['process_name']}")
    bash_cmd = f'cd "{config["directory"]}";{config["launch_command"]}'
    screen_cmd = f'screen -A -m -d -S {config["process_name"]} bash -c "{bash_cmd}"'
    Popen(screen_cmd, shell=True)  # nosec


def check(config: Dict) -> bool:
    screens_list_output = ""
    try:
        process_output = check_output(["screen", "-list"])
        screens_list_output = process_output.decode().lower()
    except CalledProcessError as e:
        exception_output = e.output
        screens_list_output = exception_output.decode()

    running_processes = findall(r"[0-9]*\.(.*?)\t", screens_list_output.lower())

    if config["process_name"] not in running_processes:
        print(f"[{get_est_time()}] {config['process_name']} not running")
        return False
    return True


def main_loop(bot_config: Dict):
    print(f"[{get_est_time()}] Started monitoring")
    while True:
        bot_active = check(bot_config)
        if not bot_active:
            launch(bot_config)
        sleep(1)


def main_init():
    print(f"[{get_est_time()}] Initializing...")
    parser = ArgumentParser(description="Discord bot arguments.")
    parser.add_argument(
        "--config", help="Filepath for the config JSON file", default="config.json"
    )
    args = parser.parse_args()
    config_file_name = str(args.config)
    with open(config_file_name, "r", encoding="utf-8") as config_file:
        loaded_config = load_json(config_file)
    config = loaded_config["watchdog"]
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

    print(f"[{get_est_time()}] Initialized")
    bot_active = check(config["bot_vars"])
    print(f"[{get_est_time()}] Bot is {'active' if bot_active else 'inactive'}")

    main_loop(config["bot_vars"])


if __name__ == "__main__":
    main_init()
