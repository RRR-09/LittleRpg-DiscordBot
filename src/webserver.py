from datetime import datetime
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv(verbose=True)
app = FastAPI()


@app.get("/")
def read_root():
    return 0


@app.get("/donations/{donations_token}")
def update_item(donations_token: str):
    print(donations_token)
    print(getenv("DONATIONS_TOKEN"))
    if donations_token != getenv("DONATIONS_TOKEN"):
        return 0  # TODO: Make a competent security system

    path = Path.cwd() / "data" / "monthly_progress"
    current_goal_month = f"{datetime.now().strftime('%Y-%m')}.dat"
    current_income = 0.0

    try:
        with open(path / current_goal_month, "r") as data_file:
            current_income = float(data_file.read())
    except FileNotFoundError:
        Path(path).mkdir(exist_ok=True)
        with open(path / current_goal_month, "w") as data_file:
            data_file.write(str(current_income))
    percentage = round((current_income / int(getenv("DONATIONS_GOAL", 100))) * 100)

    return percentage
