from time import time
from fastapi import FastAPI, Form, Request, __version__
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
#async def check(request: Request, nonce: str = Form(...), timestamp: str = Form(...), echostr: str = Form(...), signature: str = Form(...)) -> str:
async def check(request: Request) -> bool:
    # application/x-www-form-urlencoded
    # body = await request.body()
    form = await request.form()
    nonce = form.get("nonce")
    timestamp = form.get("timestamp")
    echostr = form.get("echostr")
    signature = form.get("signature")
    logging.info(f"nonce: {nonce}, timestamp: {timestamp}, echostr: {echostr}, signature: {signature}")
    cat_string = ''.join(sorted([timestamp, nonce, token]))
    if hashlib.sha1(cat_string.encode()).hexdigest() == signature:
        logging.info(f"check success, echostr: {echostr}")
        return True
    else:
        logging.error("check failed")
        return False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
