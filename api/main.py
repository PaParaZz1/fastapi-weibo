from typing import Tuple
from fastapi import FastAPI, Request, __version__
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import os
import re
import time
import json
import logging
import hashlib
import requests
import asyncio
from api.llm import call_llm
from api.kv import KV


logging.getLogger().setLevel(logging.INFO)
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
all_tasks = asyncio.Queue()
kv = KV()
token = os.getenv("WEIBO_TOKEN")

html = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>FastAPI on Vercel</title>
        <link rel="icon" href="/static/favicon.ico" type="image/x-icon" />
    </head>
    <body>
        <div class="bg-gray-200 p-4 rounded-lg shadow-lg">
            <h1>Hello from FastAPI@{__version__}</h1>
            <ul>
                <li><a href="/docs">/docs</a></li>
                <li><a href="/redoc">/redoc</a></li>
            </ul>
            <p>Powered by <a href="https://vercel.com" target="_blank">Vercel</a></p>
        </div>
    </body>
</html>
"""


@app.get("/")
async def root():
    # return HTMLResponse(html)
    # set 404 for the root path to ensure the safety
    return HTMLResponse(status_code=404, content="Not Found")


@app.get('/ping')
async def hello():
    # naive health check
    return {'res': 'pong', 'version': __version__, "time": time.time()}


class WeiboClient:
    def __init__(self):
        self.retry = 3

    def check_token(self) -> Tuple[bool, str]:
        """
        Check if the token is set and not expired, if so, return True and the token, otherwise return False and None
        """
        logging.info("check token begin")
        access_token = kv.get("access_token")
        logging.info(f"check token end {access_token}")
        if access_token is None:
            return False, None
        else:
            access_token = access_token.replace("'", '"')
            access_token = json.loads(access_token)
            # 60 is the update time for the token, the expire time of the token defined by weibo is 2 hour
            if (time.time() - access_token["created_at"]) >= 60:
                logging.info(f"need to update token: {access_token}")
                return False, None
            else:
                return True, access_token["token"]

    def update_token(self) -> str:
        """
        update token with the special weibo api for bot
        """
        logging.info("begin to update token")
        app_key = os.getenv('APP_KEY')
        app_secret = os.getenv('APP_SECRET')
        uid = os.getenv('DEV_UID')
        assert app_key is not None
        assert app_secret is not None
        assert uid is not None
        md5_hash = hashlib.md5()

        current_time_sec = time.time()
        timestamp = str(int(round(current_time_sec * 1000)))
        data = {
            'client_id': app_key,
            'timestamp': timestamp,
            'nonce': 'eqiojronqnr',
        }
        sign = '&'.join([data['client_id'], uid, data['timestamp'], data['nonce'], app_secret])
        md5_hash.update(sign.encode())
        data['sign'] = md5_hash.hexdigest()
        logging.info(f'update_token: {data}, uid: {uid}')
        url = 'https://api.weibo.com/oauth2/vp/authorize?client_id=' + data['client_id'] + '&timestamp=' + data['timestamp'] + '&nonce=' + data['nonce'] + '&sign=' + data['sign']
        response = requests.get(url)
        data = response.json()
        access_token = data.get("access_token")
        kv.set("access_token", {"token": access_token, "created_at": current_time_sec})
        logging.info("update token success")
        return access_token

    def _get_access_token(self):
        flag, access_token = self.check_token()
        if flag:
            return access_token
        else:
            return self.update_token()

    def comment_reply(self, cid: str, sid: str, rip: str, text: str = None, image_url: str = None):
        access_token = self._get_access_token()
        if text is None:
            text = "已收到评论，飞速运转中..." + str(time.ctime())
        url = "https://api.weibo.com/2/comments/reply.json"
        data = {
            "access_token": access_token,
            "cid": cid,
            "id": sid,
            "comment": text,
            "rip": rip,
        }
        # if indicated image_url is None, use the bottom image (qr code) as the default image
        if image_url is not None:
            # weibo image_url example: https://wx1.sinaimg.cn/large/0072Vf1pgy1gq1z1z1z1rj30u00u0q4f.jpg
            pic_ids = image_url.split("/")[-1].split(".")[0]
            data["pic_ids"] = pic_ids

        # retry `self.retry` times if the status code is not 200 (network error or expired token)
        for _ in range(self.retry):
            logging.info(f"comment_reply: {data}")
            res = requests.post(url, data=data)
            if res.status_code != 200:
                error_text = res.text
                logging.info(f"text: {error_text} token: {access_token}")
                error_data = json.loads(error_text)
                # 21332 means the token is expired
                if error_data["error_code"] == 21332:
                    data["access_token"] = self.update_token()
            else:
                break

    def comment_create(self, sid: str, rip: str, text: str = None, image_url: str = None):
        access_token = self._get_access_token()
        if text is None:
            text = "已收到at微博，飞速运转中..." + str(time.ctime())
        url = "https://api.weibo.com/2/comments/create.json"
        data = {
            "access_token": access_token,
            "id": sid,
            "comment": text,
            "rip": rip,
        }
        # if indicated image_url is None, use the bottom image (qr code) as the default image
        if image_url is not None:
            # weibo image_url example: https://wx1.sinaimg.cn/large/0072Vf1pgy1gq1z1z1z1rj30u00u0q4f.jpg
            pic_ids = image_url.split("/")[-1].split(".")[0]
            data["pic_ids"] = pic_ids
        # retry `self.retry` times if the status code is not 200 (network error or expired token)
        for _ in range(self.retry):
            logging.info(f"comment_create: {data}")
            res = requests.post(url, data=data)
            if res.status_code != 200:
                error_text = res.text
                logging.info(f"text: {error_text} token: {access_token}")
                error_data = json.loads(error_text)
                # 21332 means the token is expired
                if error_data["error_code"] == 21332:
                    data["access_token"] = self.update_token()
            else:
                break

    def upload_image(self, image_url: str):
        access_token = self._get_access_token()
        url = "https://api.weibo.com/2/statuses/upload_pic.json"
        files = {
            "pic": requests.get(image_url).content,
            "access_token": (None, access_token),
        }
        # retry `self.retry` times if the status code is not 200 (network error or expired token)
        for _ in range(self.retry):
            logging.info(f"upload_image: {image_url}")
            res = requests.post(url, files=files)
            if res.status_code != 200:
                error_text = res.text
                logging.info(f"text: {error_text} token: {access_token}")
                error_data = json.loads(error_text)
                # 21332 means the token is expired
                if error_data["error_code"] == 21332:
                    files["access_token"] = self.update_token()
            else:
                # return res.json().get("bmiddle_pic")
                return res.json().get("original_pic")  # original_pic is the highest resolution


weibo_client = WeiboClient()
text_at = "@MBTI分院帽之电子聊愈版"
text_analysis = "微博分析ai"
text_analysis_prefix = "请你根据下列博文进行MBTI相关的分析："
text_img = "请你结合下面的图片描述回答用户的问题，以下是图片描述信息："
text_img = "\n以下是用户的问题："


def get_client_real_ip(r: Request):
    """
    Get the real ip of the client in the production environment
    """
    ip = r.headers.get("X-Real-Ip")
    if ip:
        return ip
    ip = r.headers.get("X-Forwarded-For")
    if ip:
        return ip
    if ":" in r.remote_addr:
        return r.remote_addr.split(":")[0]
    return r.remote_addr


async def async_task(fn):
    fn()
    return True


def check_repeat_status(id_: str):
    """
    Sometimes weibo will repeatedly push the data if it not received the response in time (about 5s)
    Check whether the status is already processing
    """
    data = kv.get(id_)
    if data is None:
        kv.set(id_, 'is_processing')
        return False
    else:
        return True


def check_repeat_comment(id_, sid):
    """
    Sometimes weibo will repeatedly push the data if it not received the response in time (about 5s)
    Check whether the comment is already processing
    """
    key = id_ + sid
    data = kv.get(key)
    if data is None:
        kv.set(key, 'is_processing')
        return False
    else:
        return True


def split_string_from_symbol(input_string):
    input_list = re.split(r'(，|。|；)', input_string)

    input_list = [input_list[i] for i in range(len(input_list)) if input_list[i]]
    if len(input_list) % 2 == 0:
        input_list = [input_list[i] + input_list[i+1] for i in range(0, len(input_list), 2)]
    else:
        last = input_list[len(input_list) - 1]
        input_list = [input_list[i] + input_list[i+1] for i in range(0, len(input_list) - 1, 2)]
        input_list.append(last)

    formatted_string_list = []
    formatted_string = ''
    for s in input_list:
        if len(s) + len(formatted_string) > 140:
            formatted_string_list.append(formatted_string)
            formatted_string = s
        else:
            formatted_string += s

    if len(formatted_string) > 0:
        formatted_string_list.append(formatted_string)

    return formatted_string_list


def get_vlm_result(image_url: str) -> str:
    url = os.getenv("VLM_BACKEND_ENDPOINT")
    data = {
        "image_url": image_url
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=data, headers=headers, verify=False)
    if response.status_code == 200:
        return response.text
    else:
        return None


@app.post('/upload')
async def upload(image_url: str) -> str:
    """
    Debug endpoint for the image upload
    """
    url = "https://api.weibo.com/2/statuses/upload_pic.json"
    files = {
        "pic": requests.get(image_url).content,
        "access_token": (None, weibo_client.access_token),
    }
    res = requests.post(url, files=files)
    if res.status_code != 200:
        logging.info(f"text: {res.text} token: {files['access_token']}")
        return ""
    else:
        return res.json().get("bmiddle_pic")


@app.post('/check')
async def check(request: Request) -> bool:
    """
    Main endpoint for the weibo
    """
    # application/x-www-form-urlencoded
    # body = await request.body()
    form = await request.form()
    timestamp = form.get("timestamp")
    signature = form.get("signature")
    echostr = form.get("echostr")

    # response for the normal weibo data push
    if echostr is None:  # normal request
        rip = request.client.host
        event_type = form.get("event")  # add, repost, del
        if event_type.lower() != "add":
            return JSONResponse({"result": True, "pull_later": False, "message": ""})
        content_type = form.get("content_type")  # status, comment
        content_body = form.get("content_body")
        content_body = json.loads(content_body)

        id_ = content_body.get("id")
        text = content_body.get("text")
        uid = content_body.get("user").get("id")
        screen_name = content_body.get("user").get("screen_name")
        if content_type == "status":
            if text_at not in text:
                logging.info(f"user own post: {uid}, {screen_name}, {text}")
                return JSONResponse({"result": True, "pull_later": False, "message": ""})
            if check_repeat_status(id_):
                return JSONResponse({"result": True, "pull_later": False, "message": ""})
            has_image = content_body.get("has_image")
            images = content_body.get("images", [])
            if has_image and len(images) > 0:
                img_text = get_vlm_result(images[0])
                if img_text is not None:
                    text = text_img + img_text + text_img2 + text
                    logging.info(f"[comment img]: {img_text}")
                logging.info(f"[status] uid: {uid}, screen_name: {screen_name}, text: {text}, images: {images}")
            else:
                logging.info(f"[status] uid: {uid}, screen_name: {screen_name}, text: {text}")

            def _task():
                llm_text = call_llm(text)
                formatted_text = split_string_from_symbol(llm_text)
                for t in formatted_text:
                    weibo_client.comment_create(sid=id_, rip=rip, text=t)

            task = asyncio.create_task(async_task(_task))
            all_tasks.put_nowait(task)

        elif content_type == "comment":
            status_id = content_body.get("status").get("id")
            status_text = content_body.get("status").get("text")
            has_image = content_body.get("has_image")
            images = content_body.get("images", [])
            if check_repeat_comment(id_, status_id):
                return JSONResponse({"result": True, "pull_later": False, "message": ""})
            if has_image and len(images) > 0:
                img_text = get_vlm_result(images[0])
                if img_text is not None:
                    text = text_img + img_text + text_img2 + text
                    logging.info(f"[comment img]: {img_text}")
                logging.info(f"[comment] uid: {uid}, screen_name: {screen_name}, text: {text}, status_id: {status_id}, status_text: {status_text}, images: {images}")
            else:
                logging.info(f"[comment] uid: {uid}, screen_name: {screen_name}, text: {text}, status_id: {status_id}, status_text: {status_text}")
            if text_analysis in text.lower():
                text = text_analysis_prefix + status_text

            def _task():
                llm_text = call_llm(text)
                formatted_text = split_string_from_symbol(llm_text)
                for t in formatted_text:
                    weibo_client.comment_reply(cid=id_, sid=status_id, rip=rip, text=t)

            task = asyncio.create_task(async_task(_task))
            all_tasks.put_nowait(task)

        return JSONResponse({"result": True, "pull_later": False, "message": ""})
    # response for the weibo validation request
    else:
        nonce = form.get("nonce")
        logging.info(f"nonce: {nonce}, timestamp: {timestamp}, echostr: {echostr}, signature: {signature}")
        cat_string = ''.join(sorted([timestamp, nonce, token]))
        if hashlib.sha1(cat_string.encode()).hexdigest() == signature:
            logging.info(f"check success, echostr: {echostr}")
            return PlainTextResponse(content=echostr)
        else:
            logging.error("check failed")
            return PlainTextResponse(content='', status_code=403)


@app.on_event("shutdown")
async def shutdown_event():
    while not all_tasks.empty():
        logging.info(f"begin wait {time.ctime()}")
        task = all_tasks.get_nowait()
        await task
        logging.info(f"end wait {time.ctime()}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
