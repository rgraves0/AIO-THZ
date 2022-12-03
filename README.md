## Heroku Deploy
Use the below button to deploy the bot in Heroku.

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)


# AIO-Music-Helper-Bot
Telegram bot to manage all your music needs.

## ⚠️ WORK IN PROGRESS ⚠️


## Deploy VPS METHOD-1

Change.env add variable

## Add New Screen

```
sudo apt install tmux
tmux ls
tmux new -s session_name
tmux a -t session_name
tmux kill-session -t session_name

```

```

sudo apt install python3-virtualenv

virtualenv -p python3 VENV

. ./VENV/bin/activate

pip install -r requirements.txt

pip install psycopg2-binary 

python -m bot

```
- For Database URL use Heroku Postgres (if on Heroku) or ElephantSQL

## Deploy VPS METHOD-2 (STABIL) AND BASIC

- Start Docker daemon (skip if already running), if installed by snap then use 2nd command:
    
        sudo dockerd
        sudo snap start docker

     Note: If not started or not starting, run the command below then try to start.

        sudo apt install docker.io

- Build Docker image:

        sudo docker build . -t aio-music-bot

- Run the image:

        sudo docker run aio-music-bot

- To stop the image:

        sudo docker ps
        sudo docker stop id

- To clear the container:

        sudo docker container prune

- To delete the images:

        sudo docker image prune -a







## Bot Commads Details
#### Info about available commands for the bot
#### Authentication is done in the settings panel. Use /settings command
#### Copy paste these commands in BotFather

```
start - Start the bot
download - dl
auth - auth user [Admin Only]
admin_settings - settings [Admin Only]

```
