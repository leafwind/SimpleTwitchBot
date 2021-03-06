# -*- coding: utf-8 -*-
from twisted.words.protocols import irc
from twisted.internet import reactor
from collections import defaultdict
from commands import Permission
import threading
from threading import Thread
import traceback
import commands
import requests
import logging
import signal
import json
import time
import sqlite3

from markov_chain import MarkovChat
from twitch_utils import get_stream_status, get_current_users

USERLIST_API = "http://tmi.twitch.tv/group/user/{}/chatters"
with open('config.json') as fp:
    CONFIG = json.load(fp)

class StreamStatus(object):
    global CONFIG
    def __init__(self, channel):
        self.channel = channel
        self.is_live = False
        conn = sqlite3.connect(CONFIG['db'])
        c = conn.cursor()
        c.execute('''create table if not exists stream (id INTEGER, channel TEXT, game TEXT, created_at INTEGER, end_at INTEGER, PRIMARY KEY (id) ON CONFLICT REPLACE);''')
        c.execute('''create table if not exists channel_popularity (channel TEXT, ts INTEGER, n_user INTEGER, PRIMARY KEY (channel, ts) ON CONFLICT REPLACE);''')
        c.execute('''create table if not exists chat (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, channel TEXT, ts INTEGER, msg TEXT, UNIQUE (user, channel, ts, msg) ON CONFLICT IGNORE);''')
        conn.commit()
        conn.close()

    def update(self):
        conn = sqlite3.connect(CONFIG['db'])
        c = conn.cursor()

        now = int(time.time())
        (is_live, _id, created_at_ts, game, n_user) = get_stream_status(self.channel)
        if not is_live: # offline now
            if self.is_live != is_live: # online switched to offline
                # update the end ts of the last stream (end_at = 0 means is it not updated)
                last_stream_query = '''select id, created_at from stream where channel = \'{}\' and end_at = 0 order by created_at desc limit 1;'''.format(self.channel)
                logging.info(last_stream_query)
                c.execute(last_stream_query)
                result = c.fetchall()
                if len(result) == 0:
                    logging.error("error: {} no last stream log".format(self.channel))
                else:
                    _id_last_online = result[0][0]
                    created_at_ts_last_online = result[0][1]
                    c.execute('''update stream set end_at = {} where id = {} and created_at = {};'''.format(now, _id_last_online, created_at_ts_last_online))
                    conn.commit() # prevent not sync, commmit first
                # set all end_at = 1 for remain end_at = 0 stream recored
                query = '''update stream set end_at = 1 where channel = \'{}\' and end_at = 0;'''.format(self.channel)
                c.execute(query)
            else: # continuous offline
                pass
        else: # online
            logging.warning("_id: {}, game: {}, created_at: {}, end_at: {}".format(_id, game, created_at_ts, 0))
            c.execute('''insert into stream (id, channel, game, created_at, end_at) VALUES ({}, \'{}\', \'{}\', {}, {});'''.format(_id, self.channel, game, created_at_ts, 0))

        self.is_live = is_live
        
        n_user_unofficial_api = len(get_current_users(self.channel))
        # record n_user no matter when online or offline
        logging.warning("channel: {}, ts: {}, n_user: {} ({} from unofficial API)".format(self.channel, now, n_user, n_user_unofficial_api))
        c.execute('''insert into channel_popularity (channel, ts, n_user) VALUES (\'{}\', {}, {});'''.format(self.channel, now, n_user if n_user > 0 else n_user_unofficial_api))

        conn.commit()
        conn.close()
        return

class CheckChannelStreamRepeat(Thread):
    def __init__(self, t, ch, stream_status):
        Thread.__init__(self)
        self.t = t
        self.ch = ch
        self.stream_status = stream_status

    def run(self):
        while getattr(threading.currentThread(), "do_run", True):
            try:
                self.stream_status.update()
                time.sleep(self.t)
            except Exception as e:
                logging.exception("msg in another thread")
        logging.info("close the thread: CheckChannelStreamRepeat")

class TwitchBot(irc.IRCClient, object):
    last_warning = defaultdict(int)
    last_dispatch = 0
    owner_list = CONFIG['owner_list']
    ignore_list = CONFIG['ignore_list']
    nickname = str(CONFIG['username'])
    password = str(CONFIG['oauth_key'])
    #markov = MarkovChat("train/leafwind.txt")

    host_target = False
    pause = False
    commands = []

    def __init__(self, factory):
        global CONFIG
        self.factory = factory
        #self.markov = MarkovChat(factory.channel_file, factory.model_files, factory.chattiness)
        self.channel = "#" + factory.channel
        self.stream_status = StreamStatus(factory.channel)
        self.check_table_exists()

        # update stream status per min
        self.thread = CheckChannelStreamRepeat(CONFIG['check_interval'], factory.channel, self.stream_status)
        self.thread.start()

    def check_table_exists(self):
        global CONFIG
        conn = sqlite3.connect(CONFIG['db'])
        c = conn.cursor()
        c.execute('''create table if not exists counter (item TEXT PRIMARY KEY, count INTEGER);''')
        conn.commit()
        conn.close()
        
    def signedOn(self):
        self.factory.wait_time = 1
        logging.warning("Signed on as {}".format(self.nickname))

        signal.signal(signal.SIGINT, self.manual_action)

        # When first starting, get user list
        url = USERLIST_API.format(self.channel[1:])
        data = requests.get(url).json()
        self.users = set(sum(data['chatters'].values(), []))
        self.mods = set()
        self.subs = set()

        # Get data structures stored in factory
        self.activity = self.factory.activity
        self.tags = self.factory.tags

        # Load commands
        self.reload_commands()

        # Join channel
        self.sendLine("CAP REQ :twitch.tv/membership")
        self.sendLine("CAP REQ :twitch.tv/commands")
        self.sendLine("CAP REQ :twitch.tv/tags")
        self.join(self.channel)

    def joined(self, channel):
        logging.warning("Joined %s" % channel)

    def privmsg(self, user, channel, msg):
        # Extract twitch name
        name = user.split('!', 1)[0].lower()

        # Catch twitch specific commands
        if name in ["jtv", "twitchnotify"]:
            self.jtv_command(msg)
            return

        # Log the message
        logging.info("{}: {}".format(name, msg))

        # Ignore messages by ignored user
        if name in self.ignore_list:
            return

        # Ignore message sent to wrong channel
        if channel != self.channel:
            return

        # Check if bot is paused
        if not self.pause or name in self.owner_list:
            self.process_command(name, msg)
        else:
            self.process_command("__USER__", "__UPDATE__")

        # Log user activity
        self.activity[name] = time.time()

    def modeChanged(self, user, channel, added, modes, args):
        if channel != self.channel:
            return

        # Keep mod list up to date
        func = 'add' if added else 'discard'
        for name in args:
            getattr(self.mods, func)(name)

        change = 'added' if added else 'removed'
        info_msg = "Mod {}: {}".format(change, ', '.join(args))
        logging.warning(info_msg)

    def userJoined(self, user, channel):
        '''Update userlist when user joins'''
        if channel == self.channel:
            self.users.add(user)

    def userLeft(self, user, channel):
        '''Update userlist when user leaves'''
        if channel == self.channel:
            self.users.discard(user)

    def parsemsg(self, s):
        """Breaks a message from an IRC server into its prefix, command, and arguments."""
        tags = {}
        prefix = ''
        trailing = []
        if s[0] == '@':
            tags_str, s = s[1:].split(' ', 1)
            tag_list = tags_str.split(';')
            tags = dict(t.split('=') for t in tag_list)
        if s[0] == ':':
            prefix, s = s[1:].split(' ', 1)
        if s.find(' :') != -1:
            s, trailing = s.split(' :', 1)
            args = s.split()
            args.append(trailing)
        else:
            args = s.split()
        command = args.pop(0).lower()
        return tags, prefix, command, args

    def lineReceived(self, line):
        '''Parse IRC line'''

        # First, we check for any custom twitch commands
        tags, prefix, cmd, args = self.parsemsg(line)
        if cmd == "hosttarget":
            self.hostTarget(*args)
        elif cmd == "clearchat":
            self.clearChat(*args)
        elif cmd == "notice":
            self.notice(tags, args)
        elif cmd == "privmsg":
            self.userState(prefix, tags)

        # Remove tag information
        if line[0] == "@":
            line = line.split(' ', 1)[1]

        # Then we let IRCClient handle the rest
        super(TwitchBot, self).lineReceived(line)

    def hostTarget(self, channel, target):
        '''Track and update hosting status'''
        target = target.split(' ')[0]
        if target == "-":
            self.host_target = None
            logging.warning("Exited host mode")
        else:
            self.host_target = target
            logging.warning("Now hosting {}".format(target))

    def clearChat(self, channel, target=None):
        '''Log chat clear notices'''
        if target:
            logging.warning("{} was timed out".format(target))
        else:
            logging.warning("chat was cleared")

    def notice(self, tags, args):
        '''Log all chat mode changes'''
        if "msg-id" not in tags:
            return

        msg_id = tags['msg-id']
        if msg_id == "subs_on":
            logging.warning("Subonly mode ON")
        elif msg_id == "subs_off":
            logging.warning("Subonly mode OFF")
        elif msg_id == "slow_on":
            logging.warning("Slow mode ON")
        elif msg_id == "slow_off":
            logging.warning("Slow mode OFF")
        elif msg_id == "r9k_on":
            logging.warning("R9K mode ON")
        elif msg_id == "r9k_off":
            logging.warning("R9K mode OFF")

    def userState(self, prefix, tags):
        '''Track user tags'''
        name = prefix.split("!")[0]
        self.tags[name].update(tags)

        if 'subscriber' in tags:
            if tags['subscriber'] == '1':
                self.subs.add(name)
            elif name in self.subs:
                self.subs.discard(name)

        if 'user-type' in tags:
            if tags['user-type'] == 'mod':
                self.mods.add(name)
            elif name in self.mods:
                self.mods.discard(name)

    def write(self, msg):
        '''Send message to channel and log it'''
        self.msg(self.channel, msg)
        logging.info("{}: {}".format(self.nickname, msg))

    def get_permission(self, user):
        '''Returns the users permission level'''
        if user in self.owner_list:
            return Permission.Admin
        elif user in self.mods:
            return Permission.Moderator
        elif user in self.subs:
            return Permission.Subscriber
        return Permission.User

    def process_command(self, user, msg):
        perm_levels = ['User', 'Subscriber', 'Moderator', 'Owner']
        perm = self.get_permission(user)
        msg = msg.strip()
        first = True

        # Flip through commands and execute the first one that matches
        # Check if user has permission to execute command
        # Also reduce warning message spam by limiting it to one per minute
        for cmd in self.commands:
            try:
                match = cmd.match(self, user, msg)
                if not match or not first:
                    continue
                cname = cmd.__class__.__name__
                if perm < cmd.perm:
                    if time.time() - self.last_warning[cname] < 60:
                        continue
                    self.last_warning[cname] = time.time()
                    reply = "/w {} 權限不足，需要的最小權限為 {}.".format(user, perm_levels[cmd.perm])
                    self.write(reply)
                else:
                    cmd.run(self, user, msg)
                    logging.error("running {}".format(cname))
                    #first = False
            except:
                logging.error(traceback.format_exc())

    def manual_action(self, *args):
        cmd = raw_input("Command: ").strip()
        if cmd == "q":  # Stop bot
            self.terminate()
        elif cmd == 'r':  # Reload bot
            self.reload()
        elif cmd == 'rc':  # Reload commands
            self.reload_commands()
        elif cmd == 'p':  # Pause bot
            self.pause = not self.pause
        elif cmd == 'd':  # try to enter debug mode
            IPythonThread(self).start()
        elif cmd.startswith("s"):
            # Say something as the bot
            self.write(cmd[2:])

    def jtv_command(self, msg):
        if "subscribed" in msg:
            # Someone subscribed
            logging.warning(msg)

            reply = "Thanks for subbing!"
            if " just subscribed" in msg:
                user = msg.split(' just ')[0]
                reply = "{}: {}".format(user, reply)
            elif " subscribed for" in msg:
                user = msg.split(" subscribed for")[0]
                reply = "{}: {}".format(user, reply)
            self.write(reply)

    def get_active_users(self, t=60*10):
        ''' Returns list of users active in chat in
        the past t seconds (default: 10m)'''

        now = time.time()
        active_users = []
        for user, last in self.activity.items():
            if now - last < t:
                active_users.append(user)

        return active_users

    def close_commands(self):
        # Gracefully end commands
        for cmd in self.commands:
            try:
                cmd.close(self)
            except:
                logging.error(traceback.format_exc())

    def reload_commands(self):
        logging.warning("Reloading commands")

        # Reload commands
        self.close_commands()
        cmds = reload(commands)
        self.commands = [
            cmds.OwnerCommands(self),
            cmds.Calculator(self),
            cmds.Timer(self),
            #cmds.MarkovLog(self),
            cmds.GlobalWhisperCommands(self),
            cmds.ChannelCommands(self),
            cmds.FreqReply(self),
            cmds.Log(self),
            cmds.SignIn(self),
            #cmds.StreamStatus(self),
        ]

    def reload(self):
        logging.warning("Reloading bot!")
        self.close_commands()
        self.quit()

    def terminate(self):
        # join the CheckChannelStreamRepeat thread
        self.thread.do_run = False
        self.thread.join()

        self.close_commands()
        reactor.stop()


class IPythonThread(Thread):
    def __init__(self, b):
        Thread.__init__(self)
        self.bot = b

    def run(self):
        logger = logging.getLogger()
        handler = logger.handlers[0]
        handler.setLevel(logging.ERROR)
        try:
            from IPython import embed
            bot = self.bot
            embed()
            del bot
        except ImportError:
            logging.error("IPython not installed, cannot debug.")
        handler.setLevel(logging.INFO)
