from twisted.internet import protocol, reactor
from collections import defaultdict

import bot
import time
import logging
import logging.config
import argparse
logging.config.fileConfig('logging.conf')


class BotFactory(protocol.ClientFactory):

    tags = defaultdict(dict)
    activity = dict()
    wait_time = 1

    def __init__(self, channel, chattiness, models):
        self.channel = channel
        self.channel_file = "train/" + channel + ".txt"
        self.chattiness = chattiness
        self.model_files = ["train/" + m + ".txt" for m in models if m != channel]
        print("BotFactory: channel = {}".format(self.channel))
        print("BotFactory: channel_file = {}".format(self.channel_file))
        print("BotFactory: chattiness = {}".format(self.chattiness))
        print("BotFactory: models = {}".format(self.model_files))

    #protocol = bot.TwitchBot
    def buildProtocol(self, addr):
        p = bot.TwitchBot(factory = self)
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        logging.error("Lost connection, reconnecting")
        self.protocol = reload(bot).TwitchBot
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        msg = "Could not connect, retrying in {}s"
        logging.warning(msg.format(self.wait_time))
        time.sleep(self.wait_time)
        self.wait_time = min(512, self.wait_time * 2)
        connector.connect()


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Print string')
    parser.add_argument("-c", "--channel", help="twitch channel to login")
    parser.add_argument("-q", "--chattiness", help="chance of robot to auto talk")
    parser.add_argument("-m", "--models", nargs='+', type=str, help="load multi channel's log")
    args = parser.parse_args()

    # create factory protocol and application
    f = BotFactory(args.channel, float(args.chattiness), args.models)

    # connect factory to this host and port
    reactor.connectTCP('irc.twitch.tv', 6667, f)
    reactor.run()
