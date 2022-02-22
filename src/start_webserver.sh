#!/bin/sh
screen -A -m -d -S "littlerpg-webserver" bash -c "poetry run gunicorn webserver:app -w 4 -k uvicorn.workers.UvicornWorker"


