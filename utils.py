import asyncio
import os
import traceback
from os import path

import requests
from retrying import retry
# 更换 Chromium 下载地址为非 https 淘宝源
os.environ['PYPPETEER_DOWNLOAD_HOST'] = 'http://npm.taobao.org/mirrors'
from pyppeteer import launch # 不能删，隔壁 dynamic.py 还要调用的
from pyppeteer.chromium_downloader import check_chromium, download_chromium

# 检查 Chromium 是否下载
if not check_chromium():
    download_chromium()


class BiliAPI():
    def __init__(self) -> None:
        self.default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/79.0.3945.130 Safari/537.36",
        "Referer": "https://www.bilibili.com/"
        }
    @retry
    def get(self, url, headers=None, cookies=None):
        if not headers:
            headers = self.default_headers
        with requests.Session() as sess:
            r = sess.get(url, headers=headers, cookies=cookies)
        r.encoding = 'utf-8'
        return r
    
    def get_json(self, url, **kw):
        return (self.get(url, **kw)).json()
    
    def get_info(self, uid):
        url = f'https://api.bilibili.com/x/space/acc/info?mid={uid}'
        return (self.get_json(url))['data']

    def get_dynamic(self, uid):
        # need_top: {1: 带置顶, 0: 不带置顶}
        url = f'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?host_uid={uid}&offset_dynamic_id=0&need_top=0'
        return (self.get_json(url))['data']
    
    def get_live_info(self, uid):
        url = f'https://api.live.bilibili.com/room/v1/Room/getRoomInfoOld?mid={uid}'
        return (self.get_json(url))['data']



