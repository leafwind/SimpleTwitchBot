#!/usr/bin/env python
from slackclient import SlackClient
import yaml

class Slack(object):
    def __init__(self):
        config = yaml.load(open('slack.conf', 'r'))
        token = config.get('SLACK_TOKEN')
        self.sc = SlackClient(token)
        self.channel_list = {}
        self._get_channel_list()

    def _get_channel_list(self):
        result = self.sc.api_call("channels.list")
        for channel in result["channels"]:
            self.channel_list[channel["name"]] = channel["id"]
        result = self.sc.api_call("groups.list")
        for channel in result["groups"]:
            self.channel_list[channel["name"]] = channel["id"]
        return 

    def post_message(self, channel, text, icon_emoji, username='schubot'):
        if icon_emoji == None:
            icon_emoji = ':rabbit:'
        result = self.sc.api_call("chat.postMessage", channel=channel, text=text, username=username, icon_emoji=icon_emoji)

    def get_channelname(self, channel_id):
        channel_info = self.sc.api_call("channels.info", channel=channel_id)
        if channel_info['ok'] == False:
            print channel_info
            return 'N/A'
        channelname = channel_info['channel']['name']
        return channelname
    
    def get_username(self, slack_id):
        user_info = self.sc.api_call("users.info", user=slack_id)
        username = user_info['user']['name']
        return username
    
