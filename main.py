from time import time
from fastapi import FastAPI, Request, __version__
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, JSONResponse
import os
import json
import logging
import hashlib
import requests

logging.getLogger().setLevel(logging.INFO)
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
token = os.getenv("WEIBO_TOKEN")
access_token = os.getenv("WEIBO_ACCESS_TOKEN")

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
    return {'res': 'pong', 'version': __version__, "time": time()}


def fake_comment(cid: str, sid: str):
    # url = "https://api.weibo.com/2/comments/create.json"
    url = "https://api.weibo.com/2/comments/reply.json"
    data = {
        "access_token": access_token,
        "cid": cid,
        "id": sid,
        "comment": "已收到评论，飞速运转中...",
    }
    logging.info(f"fake_comment: {data} cid: {cid}, sid: {sid}")
    res = requests.post(url, data=data)
    logging.info(f"fake_comment: {res}")


@app.post('/check')
# async def check(request: Request, nonce: str = Form(...), timestamp: str = Form(...), echostr: str = Form(...), signature: str = Form(...)) -> str:
async def check(request: Request) -> bool:
    # application/x-www-form-urlencoded
    # body = await request.body()
    form = await request.form()
    timestamp = form.get("timestamp")
    signature = form.get("signature")
    echostr = form.get("echostr")
    if echostr is None:  # normal request
        event_type = form.get("event")  # add, repost, del
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
        elif content_type == "comment":
            status_id = content_body.get("status").get("id")
            status_text = content_body.get("status").get("text")
            logging.info(f"[comment] uid: {uid}, screen_name: {screen_name}, text: {text}, status_id: {status_id}, status_text: {status_text}")
            fake_comment(cid=id_, sid=status_id)

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
