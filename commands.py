# -*- coding: utf-8 -*-
from math_parser import NumericStringParser
from threading import Thread
import time
import re
import json
import requests
import random
from slack_util import Slack
slack = Slack()

channel_commands = {}
with open('channel_commands.json') as fp:
    channel_commands_orig = json.load(fp)
    for u_channel in channel_commands_orig:
        b_channel = u_channel.encode('utf-8')
        if b_channel not in channel_commands:
            channel_commands[b_channel] = {}
        for u_cmd in channel_commands_orig[u_channel]:
            b_cmd = u_cmd.encode('utf-8')
            if b_cmd not in channel_commands[b_channel]:
                channel_commands[b_channel][b_cmd] = []
            for u_output in channel_commands_orig[u_channel][u_cmd]:
                b_output = u_output.encode('utf-8')
                channel_commands[b_channel][b_cmd].append(b_output)

with open('config.json') as fp:
    CONFIG = json.load(fp)

nickname = str(CONFIG['username'])

# Set of permissions for the commands
class Permission:
    User, Subscriber, Moderator, Admin = range(4)


# Base class for a command
class Command(object):
    perm = Permission.Admin

    def __init__(self, bot):
        pass

    def match(self, bot, user, msg):
        return False

    def run(self, bot, user, msg):
        pass

    def close(self, bot):
        pass


class MarkovLog(Command):
    '''Markov Chat bot that learns from chat
    and generates semi-sensible sentences

    You can use "!chat" to generate a completely
    random sentence, or "!chat about <context>" to
    generate a sentence containing specific words'''

    perm = Permission.User

    def match(self, bot, user, msg):
        #self.reply = bot.markov.log(msg)
        cmd = msg.lower()
        #case1 = cmd.startswith("!chat about")
        #case2 = cmd == "!chat"
        #return case1 or case2 or self.reply
        
        # new
        return cmd.startswith("!chat")# or self.reply

    def run(self, bot, user, msg):
        cmd = msg.lower()
        #if cmd == "!chat":
        #    reply = bot.markov.random_chat()
        #    bot.write(reply)
        #elif cmd.startswith("!chat about"):
        #    reply = bot.markov.chat(msg[12:])
        #    bot.write(reply)
        msg = msg[6:]
        import logging
        logging.error(msg)
        reply = bot.markov.log(msg, 1)
        bot.write(reply)

class SlackLog(Command):
    global slack
    perm = Permission.User

    def match(self, bot, user, msg):
        return True

    def run(self, bot, user, msg):
        slack.post_message(slack.channel_list[bot.factory.channel], msg, ":rabbit:", username=user)

class FightBack(Command):
    '''Simple meta-command to output a reply given
    a specific command. Basic key to value mapping.'''

    perm = Permission.User

    replies = {
	"!fight {}".format(nickname): "!fight {}",
    }

    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        for key in self.replies:
            if cmd == key:
                return True
        return False

    def run(self, bot, user, msg):
        cmd = msg.lower().strip()

        for key, reply in self.replies.items():
            if cmd == key:
                time.sleep(3)
                bot.write(reply.format(user))
                break

class SimpleReply(Command):
    '''Simple meta-command to output a reply given
    a specific command. Basic key to value mapping.'''

    perm = Permission.User

    replies = {
        "太貓啦": "太貓啦 (๑•̀ω•́)ノ",
        "!ping": "pong",
        "!headset": "Logitech G930 Headset",
        "!rts": "/me REAL TRAP SHIT",
        "!nfz": "/me NO FLEX ZONE!",
    }

    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        for key in self.replies:
            if cmd == key:
                return True
        return False

    def run(self, bot, user, msg):
        cmd = msg.lower().strip()

        for key, reply in self.replies.items():
            if cmd == key:
                bot.write(reply)
                break


class Calculator(Command):
    ''' A chat calculator that can do some pretty
    advanced stuff like sqrt and trigonometry

    Example: !calc log(5^2) + sin(pi/4)'''

    nsp = NumericStringParser()
    perm = Permission.User

    def match(self, bot, user, msg):
        return msg.lower().startswith("!calc ")

    def run(self, bot, user, msg):
        expr = msg.split(' ', 1)[1]
        try:
            result = self.nsp.eval(expr)
            if result.is_integer():
                result = int(result)
            reply = "{} = {}".format(expr, result)
            bot.write(reply)
        except:
            bot.write("{} = ???".format(expr))

class ChannelCommands(Command):
    perm = Permission.User
    def match(self, bot, user, msg):
        global channel_commands
        return True

    def run(self, bot, user, msg):
        cmd = msg.lower().strip()
        global channel_commands
        channel = bot.factory.channel
        if channel in channel_commands:
            if cmd.lstrip("!") == '會開嗎':
                day_ratio = (int(time.time()) + 8 * 3600) % 86400 / 3600.0
                if day_ratio < 10.0:
                    bot.write("早上有開就是會開, 沒開就是不會開 ლ(╹◡╹ლ)")
                elif day_ratio < 14.0:
                    bot.write("下午有開就是會開, 沒開就是不會開 ლ(╹◡╹ლ)")
                elif day_ratio < 22.0:
                    bot.write("晚上有開就是會開, 沒開就是不會開 ლ(╹◡╹ლ)")
                else:
                    bot.write("明天有開就是會開, 沒開就是不會開 ლ(╹◡╹ლ)")
            elif cmd.lstrip("!") in channel_commands[channel]:
                output = random.choice(channel_commands[channel][cmd.lstrip("!")])
                bot.write("{}".format(output))

class StreamStatus(Command):
    global slack
    perm = Permission.User
    online = False

    def get_status(self, bot):
        url = 'https://api.twitch.tv/kraken/streams/' + bot.factory.channel
        headers = {'Accept': 'application/vnd.twitchtv.v3+json'}
        r = requests.get(url, headers=headers)
        info = json.loads(r.text)
        if 'stream' not in info or info['stream'] == None:
            (self.n_user, self.created_at) = (0, "")
            return False
        else:
            self.n_user = info['stream']['viewers']
            self.created_at = info['stream']['created_at']
            return True

    def match(self, bot, user, msg):
        current_status = self.get_status(bot)
        #print("last: {}, current: {}".format(self.online, current_status))
        if self.online != current_status:
            self.online = current_status
            return True
        else:
            return False

    def run(self, bot, user, msg):
        if self.online:
            slack.post_message(slack.channel_list[bot.factory.channel], "<!group> 開台囉！", ":rabbit:", username=user)
        else:
            slack.post_message(slack.channel_list[bot.factory.channel], "<!group> 關台哭哭喔～～！", ":rabbit:", username=user)


class RandomGive(Command):
    perm = Permission.User
    def match(self, bot, user, msg):
        url = 'https://api.twitch.tv/kraken/streams/' + bot.factory.channel
        headers = {'Accept': 'application/vnd.twitchtv.v3+json'}
        r = requests.get(url, headers=headers)
        info = json.loads(r.text)
        if 'stream' not in info or info['stream'] == None:
            return False
        if 'viewers' in info['stream'] and time.time() - bot.last_dispatch > 1800: # every 30 mins
            if bot.last_dispatch > 0:
                if len(bot.get_active_users()) > 0:
                    lucky_user = random.choice(bot.get_active_users())
                    bot.write("!coins pay {} 1".format(lucky_user))
            bot.last_dispatch = time.time()
            return True
        else:
            return False
    def run(self, bot, user, msg):
        pass

class Timer(Command):
    '''Sets a timer that will alert you when it runs out'''
    perm = Permission.Moderator

    def match(self, bot, user, msg):
        return msg.lower().startswith("!timer")

    def run(self, bot, user, msg):
        cmd = msg.lower()
        if cmd == "!timer":
            bot.write("Usage: !timer 30s or !timer 5m")
            return

        arg = cmd[7:].replace(' ', '')
        match = re.match("([\d\.]+)([sm]).*", arg)
        if match:
            d, u = match.groups()
            t = float(d) * (60 if u == 'm' else 1)
            thread = TimerThread(bot, user, t)
            thread.start()
        elif arg.isdigit():
            thread = TimerThread(bot, user, int(arg) * 60)
            thread.start()
        else:
            bot.write("{}: Invalid argument".format(user))


class TimerThread(Thread):
    def __init__(self, b, u, t):
        Thread.__init__(self)
        self.bot = b
        self.user = u
        self.time = int(t)

    def run(self):
        secs = self.time % 60
        mins = self.time / 60

        msg = "{}: Timer started for".format(self.user)
        if mins > 0:
            msg += " {}m".format(mins)
        if secs > 0:
            msg += " {}s".format(secs)

        self.bot.write(msg)
        time.sleep(self.time)
        self.bot.write("{}: Time is up!".format(self.user))


class OwnerCommands(Command):
    '''Some miscellaneous commands for bot owners'''

    perm = Permission.Admin

    def match(self, bot, user, msg):
        cmd = msg.lower().replace(' ', '')
        if cmd.startswith("!sleep"):
            return True
        elif cmd.startswith("!wakeup"):
            return True
        elif cmd.startswith("!say"):
            return True

        return False

    def run(self, bot, user, msg):
        cmd = msg.lower().replace(' ', '')
        if cmd.startswith("!sleep"):
            bot.write("(๑•̀ω•́)ノ洗洗睡去")
            bot.pause = True
        elif cmd.startswith("!wakeup"):
            bot.write("(๑•̀ω•́)ノ早安")
            bot.pause = False
        elif cmd.startswith("!say"):
            bot.write(msg[4:].lstrip(" "))

