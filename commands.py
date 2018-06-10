# -*- coding: utf-8 -*-
from math_parser import NumericStringParser
from threading import Thread
import time
import re
import json
import logging
import requests
import random
import freq_reply
import sqlite3
import calendar

from slack_util import Slack
slack = Slack()

count_freq = {}

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

global_whisper_commands = {}
with open('global_whisper_commands.json') as fp:
    global_whisper_commands_orig = json.load(fp)
    for u_cmd in global_whisper_commands_orig:
        b_cmd = u_cmd.encode('utf-8')
        if b_cmd not in global_whisper_commands:
            global_whisper_commands[b_cmd] = []
        for u_output in global_whisper_commands_orig[u_cmd]:
            b_output = u_output.encode('utf-8')
            global_whisper_commands[b_cmd].append(b_output)

with open('config.json') as fp:
    CONFIG = json.load(fp)

nickname = str(CONFIG['username'])
client_id = str(CONFIG['client_id'])

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
        logging.error(msg)
        reply = bot.markov.log(msg, 1)
        bot.write(reply)

class Log(Command):
    global CONFIG
    global slack
    perm = Permission.User

    def match(self, bot, user, msg):
        return True

    def run(self, bot, user, msg):
        now = int(time.time())
        channel = bot.factory.channel
        if channel == 'wow_tomato':
            slack.post_message(slack.channel_list[bot.factory.channel], msg, ":rabbit:", username=user)

        logging.warning("user: {}, channel: {}, ts: {}, msg: {}".format(user, channel, now, msg))
        conn = sqlite3.connect(CONFIG['db'])
        c = conn.cursor()
        c.execute('''insert into chat (user, channel, ts, msg) VALUES (\'{}\', \'{}\', {}, \'{}\');'''.format(user, channel, now, msg))
        conn.commit()
        conn.close()

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

class FreqReply(Command):
    global count_freq
    perm = Permission.User
    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        channel = bot.factory.channel
        if channel in freq_reply.mapping:
            mapping = freq_reply.mapping[channel]
            for key in mapping:
                for trigger in mapping[key]["trigger_list"]:
                    if trigger in cmd:
                        return True
        return False

    def run(self, bot, user, msg):
        cmd = msg.lower().strip()
        channel = bot.factory.channel
        if channel in freq_reply.mapping:
            mapping = freq_reply.mapping[channel]
            for key in mapping:
                for trigger in mapping[key]["trigger_list"]:
                    if trigger in cmd:
                        if channel not in count_freq:
                            count_freq[channel] = {}
                        if key not in count_freq[channel]:
                            count_freq[channel][key] = {}
                        now = int(time.time())
                        begin = count_freq[channel][key].get("begin", 0)
                        count = count_freq[channel][key].get("count", 0)
                        freq = mapping[key].get("freq", 3)
                        if now - begin > 60 and freq > 1:
                            begin = now
                            count = 1
                            print("reset {} counter - begin ts: {}, count: {}, freq: {}".format(key, begin, count, freq))
                        else:
                            count += 1
                            print("++ {} counter - begin ts: {}, count: {}, freq: {}".format(key, begin, count, freq))
                            if count >= freq:
                                msg = "@{} {}".format(user, mapping[key]["response"])
                                bot.write(msg)
                                begin = 0
                                count = 0
                                print("write msg: {}".format(msg))
                        count_freq[channel][key] = {"begin": begin, "count": count}

class GlobalWhisperCommands(Command):
    perm = Permission.User
    global global_whisper_commands
    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        channel = bot.factory.channel
        if cmd.lstrip("!") in global_whisper_commands:
            return True
        return False

    def run(self, bot, user, msg):
        cmd = msg.lower().strip()
        channel = bot.factory.channel
        if channel in channel_commands:
            if cmd.lstrip("!") == 'oripyon':
                for output in global_whisper_commands[cmd.lstrip("!")]:
                    bot.write("/w {} {}".format(user, output))
            elif cmd.lstrip("!") in global_whisper_commands:
                output = random.choice(global_whisper_commands[cmd.lstrip("!")])
                bot.write("/w {} {}".format(user, output))

class ChannelCommands(Command):
    perm = Permission.User
    global channel_commands
    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        channel = bot.factory.channel
        if channel in channel_commands:
            if cmd.lstrip("!") in channel_commands[channel] or cmd.lstrip("!") == '會開嗎':
                return True
        return False

    def run(self, bot, user, msg):
        cmd = msg.lower().strip()
        channel = bot.factory.channel
        if channel in channel_commands:
            if cmd.lstrip("!") == '會開嗎':
                day_ratio = (int(time.time()) + 8 * 3600) % 86400 / 3600.0
                if day_ratio < 10.0:
                    bot.write("早上有開就是會開，沒開就是不會開 ლ(╹◡╹ლ)")
                elif day_ratio < 14.0:
                    bot.write("下午有開就是會開，沒開就是不會開 ლ(╹◡╹ლ)")
                elif day_ratio < 22.0:
                    bot.write("晚上有開就是會開，沒開就是不會開 ლ(╹◡╹ლ)")
                else:
                    bot.write("明天有開就是會開，沒開就是不會開 ლ(╹◡╹ლ)")
            elif cmd.lstrip("!") in channel_commands[channel]:
                output = random.choice(channel_commands[channel][cmd.lstrip("!")])
                bot.write("{}".format(output))

class Counter(Command):
    #TODO: counter for something, maybe only for moderator
    perm = Permission.Moderator

    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        if cmd in ["!sign", "!簽到", "!打卡"]:
            return True
        else:
            return False

    def run(self, bot, user, msg):
        global CONFIG
        conn = sqlite3.connect(CONFIG['db'])
        c = conn.cursor()
        result = c.fetchall()
        if len(result) != 0:
            pass
        else:
            c.execute('''INSERT OR REPLACE INTO coins (user, coins)
                        VALUES ( \'{}\', COALESCE((SELECT coins FROM coins WHERE user = \'{}\'), 0) );'''
                        .format(user, user)
                    )
            c.execute('''UPDATE coins SET coins = coins + {} WHERE user = \'{}\';'''.format(coins, user))
            conn.commit()
            result = c.fetchall()
            bot.write("{} 簽到成功！累積簽到 {} 次，已經上課 {} 分鐘囉快坐好吧".format(user, result[0][0], self.minutes_passed))
        conn.close()

class SignIn(Command):
    perm = Permission.User
    online = False

    def get_status(self, bot):
        global client_id
        url = 'https://api.twitch.tv/kraken/streams/' + bot.factory.channel
        headers = {'Accept': 'application/vnd.twitchtv.v3+json', 'Client-ID': client_id}
        r = requests.get(url, headers=headers)
        info = json.loads(r.text)
        if 'stream' not in info or info['stream'] == None:
            (self.n_user, self.created_at) = (0, "")
            return False
        else:
            self.n_user = info['stream']['viewers']
            self.created_at = info['stream']['created_at']
            struct_time_created = time.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ")
            ts_created = calendar.timegm(struct_time_created)
            self.minutes_passed = int((self.now - ts_created) / 60)
            return True

    def match(self, bot, user, msg):
        cmd = msg.lower().strip()
        if cmd in ["!sign", "!簽到", "!打卡"]:
            return True
        else:
            return False

    def run(self, bot, user, msg):
        global CONFIG
        self.now = int(time.time())
        self.ts_day = int(self.now / 86400.0) * 86400
        self.online = self.get_status(bot)
        prompt = "/w {} 由於密語不穩定，若沒回應自己去這裡查 (́◉◞౪◟◉‵) https://ori.leafwind.tw/signin/{}/{}".format(user, bot.factory.channel, user)
        if self.online:
            conn = sqlite3.connect(CONFIG['db'])
            c = conn.cursor()
            c.execute('''create table if not exists signin (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, ts_day INTEGER, channel TEXT, UNIQUE (user, ts_day, channel) ON CONFLICT IGNORE)''')
            conn.commit()
            c.execute('''SELECT 1 from signin where user = \'{}\' and ts_day = {} and channel = \'{}\';'''.format(user, self.ts_day, bot.factory.channel))
            result = c.fetchall()
            if len(result) != 0:
                bot.write("/w {} 今天已經簽到成功囉，目前一天只開放簽到一次唷 ᕙ( ･ㅂ･)ᕗ ".format(user))
                bot.write(prompt)
            else:
                c.execute('''insert into signin (user, ts_day, channel) VALUES (\'{}\', {}, \'{}\');'''.format(user, self.ts_day, bot.factory.channel))
                conn.commit()
                c.execute('''SELECT count(1) from signin where user = \'{}\' and channel = \'{}\';'''.format(user, bot.factory.channel))
                result = c.fetchall()
                bot.write("/w {} 簽到成功！累積簽到 {} 次，已經上課 {} 分鐘囉快坐好吧".format(user, result[0][0], self.minutes_passed))
                bot.write(prompt)
            conn.close()
        else:
            bot.write("/w {} 現在不是上課時間，不能簽到喔！ _(┐「﹃ﾟ｡)_".format(user))
            bot.write(prompt)

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

