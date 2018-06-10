# setup

## setup config

`cp config.json.template config.json`

modify `config.json`:

```
"username": the bot user login ID
"oauth_key": the bot user login key
"client_id": the key to access channel status (https://api.twitch.tv/kraken/streams/ API)
"ignore_list": who's message will be ignored by bot
"owner_list": who's message have control to bot
"db": where to store the database, default "twitch_log.db", this db will be used by another http server project `twitch_analysis` which is run on the same host
"check_interval": how long bot will check the channel is streaming or not (seconds)
```

## setup environment

```
virtualenv __
. __/bin/activate
pip install -r requirements.txt
```

# run

previously on a screen scheme, will migrate to suprtvisord in the future
```
python twitch_irc.py --channel [channel] --chattiness 0 --models [channel]
```

**SimpleTwitchBot**
===============

This is a basic implementation of a Twitch IRC Bot coded in Python.
It contains most of the gory specifics needed to interact with Twitch chat.
I've included a couple basic commands as examples, but this is intended to just be a skeleton and not a fully featured bot.

If you want something even more barebone than this, checkout [BareboneTwitchBot](https://github.com/EhsanKia/BareboneTwitchBot).

update: enable `MarkovChat`

# Installation and usage
~~All you should need is Pyhton 2.7+ with [Twisted](https://twistedmatrix.com/trac/) installed.~~

All package needed is in requirements.txt, run:

```
sudo apt-get update; sudo apt-get install python-dev -y
sudo apt-get install libffi-dev libssl-dev # for pyOpenSSL
pip install requirements.txt
```
(python-virtualenv is recommended)

You then copy this project in a folder, configure the bot and run `twitch_irc.py`.

`python twitch_irc.py --channel [channel] --chattiness [chattiness] --models [models]`


#### Configuration:
Make sure to modify the following values in `config.json`:
- `channel`: Twitch channel which the bot will run on
- `username`: The bot's Twitch user
- `oauth_key`: IRC oauth_key for the bot user (from [here](http://twitchapps.com/tmi/))
- `owner_list`: List of Twitch users which have admin powers on bot
- `ignore_list`: List of Twitch users which will be ignored by the bot

**Warning**: Make sure all channel and user names above are in lowercase.

#### Usage:
The main command-line window will show chat log and other extra messsages.

You can enter commands by pressing CTRL+C on the command line:
- `q`: Closes the bot
- `r`: Reloads the code in `bot.py` and reconnects
- `rm`: reloads the code in `markov_chain.py`
- `ra`: reloads the code in `commands.py` and reloads commands
- `p`: Pauses bot, ignoring commands from non-admins
- `t <msg>`: Runs a test command with the bot's reply not being sent to the channel
- `s <msg>`: Say something as the bot in the channel

As you can see, the bot was made to be easy to modify live.
You can simply modify most of the code and quickly reload it.
The bot will also auto-reconnect if the connection is lost.

# Code Overview

#####`twitch_irc.py`
This is the file that you run. It just starts up a Twisted IRC connection with the bot protocol.
The bot is currently built to only run in one channel, but you can still open all the files over
to another folder with a different config and run it in parallel.

#####`bot.py`
Contains the bot IRC protocol. The main guts of the bot are here.

#####`commands.py`
This is where the commands are stored. The code is built to be modular.
Each "Command" class has:
- `perm` variable from the Permission Enum to set access level
- `__init__` function that initializes the command
- `match` function that checks if this command needs to run
- `run` function which actually runs the command
- `close` function which is used to cleanup and save things

All commands are passed the bot instance where they can get list of mods, subs and active users.
`match` and `run` are also passed the name of the user issuing the command and the message.

#####`markov_chain.py`
A simple Markov Chain chat bot which learns from chat messages and tries to generate coherent replies.
By default, it's only invoked with "!chat" or "!chat about <context>" commands, but you can change the
`chattiness` parameter in the file to a small fraction like 0.01 to have it randomly reply to people.
It usually needs a couple hundred lines of chat to really start becoming effective.

# Contact
If you have any extra questions about the code, you can send me a PM on twitch: @ehsankia
