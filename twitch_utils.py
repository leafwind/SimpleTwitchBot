import requests
import json
import time
import calendar
import logging

with open('config.json') as fp:
    CONFIG = json.load(fp)
client_id = str(CONFIG['client_id'])

USERLIST_API = "http://tmi.twitch.tv/group/user/{}/chatters"
def get_current_users(ch, user_type='all'):
    url = USERLIST_API.format(ch)
    r = requests.get(url).json()
    if user_type == 'all':
        try:
            all_users = set(sum(r['chatters'].values(), []))
        except Exception as e:
            logging.info("{}".format(r))
            logging.exception("msg in another thread:")
            all_users = set()
        return all_users
    elif user_type in ['moderators', 'staff', 'admins', 'global_mods', 'viewers']:
        users = set(r['chatters'][user_type])
        return users
    else:
        return set()

def get_stream_status(ch):
    global client_id
    url = 'https://api.twitch.tv/kraken/streams/' + ch
    headers = {'Accept': 'application/vnd.twitchtv.v3+json', 'Client-ID': client_id}
    r = requests.get(url, headers=headers)
    info = json.loads(r.text)

    # is_live, _id, created_at_ts, game, n_user
    if info['stream'] == None:
        return (False, 0, 0, "", 0)
    else:
        n_user = info['stream']['viewers']
        game = info['stream']['game']
        _id = info['stream']['_id']
        created_at_str = info['stream']['created_at']
        created_at_struct = time.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
        created_at_ts = calendar.timegm(created_at_struct)
        return (True, _id, created_at_ts, game, n_user)
