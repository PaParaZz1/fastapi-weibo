from time import time
from fastapi import FastAPI, Query, Request, __version__
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import logging
import hashlib

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
    return {'res': 'pong', 'version': __version__, "time": time()}


@app.post('/check')
#async def check(nonce: str = Query(None), timestamp: str = Query(None), echostr: str = Query(None), signature: str = Query(None)) -> str:
async def check(request: Request) -> str:
    logging.info(f"request: {request}")
    body = await request.body()
    logging.info(f"body: {body}")
    content_type = request.headers.get("Content-Type")
    logging.info(f"content_type: {content_type} headers: {request.headers}")
    nonce = await request.form("nonce")
    timestamp = await request.form("timestamp")
    echostr = await request.form("echostr")
    signature = await request.form("signature")
    logging.info(f"nonce: {nonce}, timestamp: {timestamp}, echostr: {echostr}, signature: {signature}")
    cat_string = ''.join(sorted([timestamp, nonce, token]))
    if hashlib.sha1(cat_string.encode()).hexdigest() == signature:
        logging.info("check success")
    else:
        logging.error("check failed")
    return echostr


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
