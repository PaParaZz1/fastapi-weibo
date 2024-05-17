import pytest
import time
import json

from .kv import KV


@pytest.mark.anyio
async def test():
    kv = KV()
    print(kv.has_auth())
    print(kv.set(key="sss", value="asasd"))
    print(kv.get("sss"))
    print(kv.get("access_token"))
    access_token = "eqe23eq"
    current_time_sec = time.time()
    print(kv.set("access_token1", {"token": access_token, "created_at": current_time_sec}))
    print(kv.get("access_token1"))
    a = kv.get("access_token1")
    a = a.replace("'", '"')
    print(json.loads(a)["token"])
