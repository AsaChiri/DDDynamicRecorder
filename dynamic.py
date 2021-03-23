import asyncio
import base64
import traceback
from os import path
import logging
import json

class Dynamic():
    def __init__(self, dynamic, default_name, data_path="./data"):
        self.dynamic = dynamic
        self.type = dynamic['desc']['type']
        self.id = dynamic['desc']['dynamic_id']
        self.url = "https://t.bilibili.com/" + str(self.id)
        self.time = dynamic['desc']['timestamp']
        self.uid = dynamic['desc']['user_profile']['info']['uid']
        self.name = dynamic['desc']['user_profile']['info'].get(
            'uname', default_name)
        self.img_name = f"{str(self.name)}_{str(self.uid)}_{self.id}_{str(self.time)}.png"
        self.img_path = path.join(data_path, self.img_name)
        card = json.loads(dynamic['card'])
        if self.type == 1:
            self.content = card['item']['content']
        elif self.type == 2:
            self.content = card['item']['description']
        elif self.type == 4:
            self.content = card['item']['content']
        elif self.type == 8:
            self.content = card['dynamic']+" "+card['title']+" "+card['desc']
        elif self.type == 16:
            self.content = card['item']['description']
        elif self.type == 64:
            self.content = card['title']+" "+card['summary']
        elif self.type == 256:
            self.content = card['title']
        elif self.type == 2048:
            self.content = card['vest']['content']
        else:
            self.content = ""
            
    @retry(stop_max_attempt_number=5, wait_random_min=5000, wait_random_max=10000)
    async def get_screenshot(self, browser):
        if path.isfile(self.img_path):
            return
        page = await browser.newPage()
        for _ in range(3):
            try:
                await page.goto(self.url, waitUntil="networkidle0")
                await page.setViewport(viewport={'width': 2560, 'height': 1440})
                card = await page.querySelector(".card")
                clip = await card.boundingBox()
                bar = await page.querySelector(".text-bar")
                bar_bound = await bar.boundingBox()
                clip['height'] = bar_bound['y'] - clip['y']
                await page.screenshot({'path': self.img_path, 'clip': clip})
                break
            except:
                logging.error(traceback.format_exc())
                await asyncio.sleep(1)
        await asyncio.sleep(10)
        await page.close()
