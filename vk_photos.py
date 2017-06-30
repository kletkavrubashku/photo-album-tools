import configparser
import datetime
import functools
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import vkapi
import vkapi.messages

OUTPUT_DIR_NAME = 'output'
LINKS_FILE_NAME = 'links.html'


def json_to_str(obj):
    return json.dumps(obj, ensure_ascii=False, indent=4)


def collect_links(links_out, message):
    def _parse_links(str):
        str = re.sub(r'<.*>', ' ', str)
        return re.findall(r'\S+\w\.[a-zA-Zа-яёА-ЯЁ]\S+', str)

    for str in ['url', 'body', 'text', 'description']:
        if str in message:
            links = _parse_links(message[str])
            if not links:
                continue
            owner_id = None
            for id_str in ['owner_id', 'copy_owner_id', 'from_id', 'uid']:
                if id_str in message:
                    owner_id = message[id_str]
            date = message.get('date', message.get('created', None))
            if (not owner_id or not date) and str != 'url':
                print('WARNING: message has not owner_id or date information: ', json_to_str(message))
            links_out.append({
                'owner_id': owner_id,
                'links': links,
                'date':  date
            })
    if 'type' in message and message['type'] != 'audio':
        if message['type'] == 'photos_list':
            message['type'] = 'photo_list'
        collect_links(links_out, message[message['type']])


def collect_photos(photos_out, message):
    for type in ['photo', 'photo_list']:
        if type not in message:
            continue
        for src in ['src_xxxbig', 'src_xxbig', 'src_xbig', 'src_big', 'src', 'src_small']:
            if src in message[type]:
                photos_out.append({
                    'owner_id': message[type]['owner_id'],
                    'src': message[type][src],
                    'date':  message[type]['created']
                })
                break


def collect_videos(videos_out, message):
    video_link = 'https://vk.com/video{}_{}'
    if 'video' not in message:
        return
    videos_out.append({
        'owner_id': message['video']['owner_id'],
        'link': video_link.format(message['video']['owner_id'], message['video']['vid']),
        'date': message['video']['date'],
        'access_key': message['video']['access_key'] if 'access_key' in message['video'] else '',
    })


def main():
    config = configparser.ConfigParser()
    config.read(['vk_photos_default_config.ini', 'vk_photos_config.ini'])

    app_id = config.get('application', 'id')
    app_secret_key = config.get('application', 'secret_key')

    client = vkapi.Client(app_id, app_secret_key, ['messages', 'photos'])

    data_arr = []
    for out in [0, 1]:
        if out == 0:
            print('Get inbox messages...')
        else:
            print('Get outbox messages...')
        messages = client.get_messages(out=out)
        for n, item in enumerate(messages):
            if n % 1000 == 0:
                print('\t{} from {}'.format(n, len(messages)))

            links, photos, videos = [], [], []
            try:
                vkapi.messages.process_item(item, functools.partial(collect_links, links), fwd_messages=True)
                vkapi.messages.process_attachments(item, functools.partial(collect_links, links), fwd_messages=True)
                vkapi.messages.process_attachments(item, functools.partial(collect_photos, photos), fwd_messages=True)
                vkapi.messages.process_attachments(item, functools.partial(collect_videos, videos), fwd_messages=True)
            except Exception as e:
                print(e)
                print(json_to_str(item))

            if links or photos or videos:
                data_arr.append({
                    'date': item['date'],
                    'uid': item['uid'],
                    'links': links,
                    'photos': photos,
                    'videos': videos
                })

    print('Collect uids...')
    users = []
    groups = []
    for item in data_arr:
        if not isinstance(item['uid'], int):
            continue
        if item['uid'] > 0:
            users.append(item['uid'])
        else:
            groups.append(-item['uid'])
        for link_item in item['links']:
            if not isinstance(link_item['owner_id'], int):
                continue
            if link_item['owner_id'] > 0:
                users.append(link_item['owner_id'])
            else:
                groups.append(-link_item['owner_id'])
        for photo_item in item['photos']:
            if not isinstance(photo_item['owner_id'], int):
                continue
            if photo_item['owner_id'] > 0:
                users.append(photo_item['owner_id'])
            else:
                groups.append(-photo_item['owner_id'])
        for video_item in item['videos']:
            if not isinstance(video_item['owner_id'], int):
                continue
            if video_item['owner_id'] > 0:
                users.append(video_item['owner_id'])
            else:
                groups.append(-video_item['owner_id'])

    uid_to_name = {}
    print('Resolve user names...')
    users = client.get_users(user_ids=users)
    for u in users:
        uid_to_name[u['uid']] = re.sub('[^a-zA-Zа-яёА-ЯЁ0-9 ]', '', '{} {}'.format(u['first_name'], u['last_name']))

    print('Resolve group names...')
    groups = client.get_groups(group_ids=groups)
    for g in groups:
        uid_to_name[-g['gid']] = re.sub('[^a-zA-Zа-яёА-ЯЁ0-9 ]', '', g['name'])

    print('Restructure data...')
    data_dict = {}
    for item in data_arr:
        for link_item in item['links']:
            data_dict_link_items = []
            for link in link_item['links']:
                data_dict_link_items.append({
                    'link': link,
                    'date': datetime.datetime.fromtimestamp(link_item['date']).strftime('%Y-%m-%d %H:%M:%S') if link_item['date'] else None
                })
            u_name = '{} ({})'.format(uid_to_name.get(item['uid'], item['uid']), item['uid'])
            owner_name = '{} ({})'.format(uid_to_name.get(link_item['owner_id'], link_item['owner_id']), link_item['owner_id'])

            data_dict.setdefault(u_name, {}).setdefault(owner_name, []).extend(data_dict_link_items)

        for photo_item in item['photos']:
            data_dict_photo_item = {
                'src': photo_item['src'],
                'name': datetime.datetime.fromtimestamp(photo_item['date']).strftime('IMG_%Y%m%d_%H%M%S.jpg')
            }
            u_name = '{} ({})'.format(uid_to_name.get(item['uid'], item['uid']), item['uid'])
            owner_name =  '{} ({})'.format(uid_to_name.get(photo_item['owner_id'], photo_item['owner_id']), photo_item['owner_id'])

            data_dict.setdefault(u_name, {}).setdefault(owner_name, []).append(data_dict_photo_item)

        for video_item in item['videos']:
            data_dict_video_item = {
                'link': video_item['link'],
                'access_key': video_item['access_key'],
                'date': datetime.datetime.fromtimestamp(video_item['date']).strftime('%Y-%m-%d %H:%M:%S') if video_item['date'] else None
            }
            u_name = '{} ({})'.format(uid_to_name.get(item['uid'], item['uid']), item['uid'])
            owner_name = '{} ({})'.format(uid_to_name.get(video_item['owner_id'], video_item['owner_id']), video_item['owner_id'])

            data_dict.setdefault(u_name, {}).setdefault(owner_name, []).append(data_dict_video_item)

    print('Save files...')
    shutil.rmtree(OUTPUT_DIR_NAME, ignore_errors=True)
    os.makedirs(OUTPUT_DIR_NAME)
    for key, value in data_dict.items():
        print('\t{}'.format(key))
        dir = os.path.join(OUTPUT_DIR_NAME, key)
        if not os.path.exists(dir):
            os.makedirs(dir)
        for key1, value1 in value.items():
            print('\t\t{}'.format(key1))
            dir1 = os.path.join(dir, key1)
            if not os.path.exists(dir1):
                os.makedirs(dir1)
            links = []
            for i in value1:
                if 'src' in i:
                    f_name = i['name']
                    while os.path.exists(os.path.join(dir1, f_name)) is True:
                        print("\t\t\tWARNING: '{}' already exist".format(f_name))
                        name_arr = f_name.split('.')
                        f_name = '{}0.{}'.format(name_arr[0], name_arr[1])
                    try:
                        urllib.request.urlretrieve(i['src'], os.path.join(dir1, f_name))
                    except urllib.error.HTTPError as e:
                        print("\t\t\tERROR: '{}' - code {}".format(i['src'], e.code))
                elif 'access_key' in i:
                    links.append('{0} <a href="{1}">{1}</a>_{2}'.format(i['date'], i['link'], i['access_key']))
                else:
                    links.append('{0} <a href="{1}">{1}</a>'.format(i['date'], i['link']))
            if links:
                links.sort()
                with open(os.path.join(dir1, LINKS_FILE_NAME), 'w') as f:
                    f.write('<meta charset="utf-8">')
                    f.write('<br>'.join(links))

if __name__ == '__main__':
    main()
