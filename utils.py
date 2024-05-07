import os
import time
import requests
import hashlib


if __name__ == '__main__':
    current_time_sec = time.time()
    timestamp = str(int(round(current_time_sec * 1000)))
    data = {
        'client_id': os.getenv('APP_KEY'),
        'timestamp': timestamp,
        'nonce': 'eqiojronqnr',
    }
    uid = os.getenv('DEV_UID')
    sign = '&'.join([data['client_id'], uid, data['timestamp'], data['nonce'], os.getenv('APP_SECRET')])
    md5_hash = hashlib.md5()
    md5_hash.update(sign.encode())
    data['sign'] = md5_hash.hexdigest()
    print(data, uid)
    print(f'before sign: {sign}')
    print(f'after sign: {data["sign"]}')
    url = 'https://api.weibo.com/oauth2/vp/authorize?client_id=' + data['client_id'] + '&timestamp=' + data['timestamp'] + '&nonce=' + data['nonce'] + '&sign=' + data['sign']
    print(url)
    response = requests.get(url)
    print(response.json())
