from threading import Thread
from fastapi import FastAPI, Request, __version__
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, JSONResponse
import os
import time
import json
import logging
import hashlib
import requests

logging.getLogger().setLevel(logging.INFO)
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
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
    return HTMLResponse(html)


@app.get('/ping')
async def hello():
    return {'res': 'pong', 'version': __version__, "time": time.time()}


class WeiboClient:
    def __init__(self):
        self.access_token = os.getenv("WEIBO_ACCESS_TOKEN")
        if self.access_token is None:
            self.last_update_time = 0
            self.update_token_thread = Thread(target=self.update_token, daemon=True)
            self.update_token_thread.start()

    def update_token(self):
        logging.info("update token thread start")
        app_key = os.getenv('APP_KEY')
        app_secret = os.getenv('APP_SECRET')
        uid = os.getenv('DEV_UID')
        assert app_key is not None
        assert app_secret is not None
        assert uid is not None
        md5_hash = hashlib.md5()

        while True:
            if time.time() - self.last_update_time >= 4800:
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
                self.access_token = data.get("access_token")
                self.last_update_time = time.time()
                logging.info("update token success")
            time.sleep(10)

    def comment_reply(self, cid: str, sid: str, rip: str, text: str = None):
        count = 0
        while self.access_token is None:
            time.sleep(1)
            count += 1
            if count >= 100:
                return
        if text is None:
            text = "已收到评论，飞速运转中..." + str(time.ctime())
        url = "https://api.weibo.com/2/comments/reply.json"
        data = {
            "access_token": self.access_token,
            "cid": cid,
            "id": sid,
            "comment": text,
            "rip": rip,
        }
        logging.info(f"comment_reply: {data}")
        res = requests.post(url, data=data)
        if res.status_code != 200:
            logging.info(f"text: {res.text}")

    def comment_create(self, sid: str, rip: str, text: str = None):
        count = 0
        while self.access_token is None:
            time.sleep(1)
            count += 1
            if count >= 100:
                return
        if text is None:
            text = "已收到at微博，飞速运转中..." + str(time.ctime())
        url = "https://api.weibo.com/2/comments/create.json"
        data = {
            "access_token": self.access_token,
            "id": sid,
            "comment": text,
            "rip": rip,
        }
        logging.info(f"comment_create: {data}")
        res = requests.post(url, data=data)
        if res.status_code != 200:
            logging.info(f"text: {res.text}")


weibo_client = WeiboClient()


@app.post('/check')
async def check(request: Request) -> bool:
    # application/x-www-form-urlencoded
    # body = await request.body()
    form = await request.form()
    timestamp = form.get("timestamp")
    signature = form.get("signature")
    echostr = form.get("echostr")
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
        created_at = content_body.get("created_at")
        uid = content_body.get("user").get("id")
        screen_name = content_body.get("user").get("screen_name")
        if content_type == "status":
            has_image = content_body.get("has_image")
            if has_image:
                images = content_body.get("images")
                logging.info(f"[status] uid: {uid}, screen_name: {screen_name}, text: {text}, images: {images}")
            else:
                logging.info(f"[status] uid: {uid}, screen_name: {screen_name}, text: {text}")
            weibo_client.comment_create(sid=id_, rip=rip)
        elif content_type == "comment":
            status_id = content_body.get("status").get("id")
            status_text = content_body.get("status").get("text")
            has_image = content_body.get("has_image")
            if has_image:
                images = content_body.get("images")
                logging.info(f"[comment] uid: {uid}, screen_name: {screen_name}, text: {text}, status_id: {status_id}, status_text: {status_text}, images: {images}")
            else:
                logging.info(f"[comment] uid: {uid}, screen_name: {screen_name}, text: {text}, status_id: {status_id}, status_text: {status_text}")
            weibo_client.comment_reply(cid=id_, sid=status_id, rip=rip)

        return JSONResponse({"result": True, "pull_later": False, "message": ""})
    else:  # validation request
        nonce = form.get("nonce")
        logging.info(f"nonce: {nonce}, timestamp: {timestamp}, echostr: {echostr}, signature: {signature}")
        cat_string = ''.join(sorted([timestamp, nonce, token]))
        if hashlib.sha1(cat_string.encode()).hexdigest() == signature:
            logging.info(f"check success, echostr: {echostr}")
            return Response(content=echostr)
        else:
            logging.error("check failed")
            return Response(content='', status_code=403)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
    # fake_comment(cid="5031749849974222", sid="5031749803574665", rip="127.0.0.1")
