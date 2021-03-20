import json
import logging
import os
import sys
import time
import asyncio
from datetime import datetime, timedelta
from tinydb_dict import TinyDBDict
import requests
from pyppeteer import launch  # 不能删，隔壁 dynamic.py 还要调用的
from dynamic import Dynamic
from utils import BiliAPI


def get_vdb_list():
    vdb_list_url = "https://vdb.vtbs.moe/json/list.json"
    vdb_list = None
    try:
        vdb_list = requests.get(vdb_list_url).json()
    except Exception:
        vdb_list = None
    return vdb_list

def content_filter(content,filter_list):
    for f in filter_list:
        if content.find(f) != -1:
            return True
    return False 

async def get_dyn(uid, last_time, browser, default_name, config):
    api = BiliAPI()
    dynamics = (await api.get_dynamic(uid)).get('cards', [])
    if len(dynamics) == 0:  # 没有发过动态或者动态全删的直接结束
        return

    if uid not in last_time:  # 没有爬取过这位主播就把最新一条动态时间为 last_time
        dynamic = Dynamic(dynamics[0], 
                          default_name, config['data_path'])
        if dynamic.time > datetime.now().timestamp() - timedelta(days=1).total_seconds():
            if dynamic.type not in config['exclude_types']:
                if not config['enable_filter'] or (config['enable_filter'] and content_filter(dynamic.content,config['content_filter'])):
                    await dynamic.get_screenshot(browser)
            last_time[uid] = dynamic.time
        else:
            last_time[uid] = int(datetime.now().timestamp())
        return

    for dynamic in dynamics[::-1]:  # 从旧到新取最近5条动态
        dynamic = Dynamic(dynamic,default_name, config['data_path'])
        if dynamic.time > last_time[uid]:
            if dynamic.type not in config['exclude_types']:
                if not config['enable_filter'] or (config['enable_filter'] and content_filter(dynamic.content,config['content_filter'])):
                    await dynamic.get_screenshot(browser)
            last_time[uid] = dynamic.time


async def main():
    vtb_list = {}
    last_time_path = "last_time.json"
    config = {}
    last_time = TinyDBDict(last_time_path)
    logfile_name = "Main_"+datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'.log'
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(thread)d %(threadName)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        handlers=[logging.FileHandler(os.path.join(logfile_name), "a", encoding="utf-8")])
    try:
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
            if not os.path.exists(config_path):
                print("数据路径不存在！")
        else:
            config_path = "./config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print("错误！")
        print("错误详情："+str(e))
        os.system('pause')
    browser = await launch(args=['--no-sandbox'])
    while True:
        new_list = get_vdb_list()
        try:
            if new_list:
                vtb_list = new_list
                if "vtbs" in vtb_list:
                    vtb_details = vtb_list['vtbs']
                    for vtb in vtb_details:
                        new_config = None
                        try:
                            with open(config_path, "r", encoding="utf-8") as f:
                                new_config = json.load(f)
                        except Exception as e:
                            print("错误！")
                            print("错误详情："+str(e))
                            new_config = None
                        if new_config:
                            config = new_config
                        if not os.path.exists(config['data_path']):
                            os.makedirs(config['data_path'])
                        name = vtb['name'][vtb['name']['default']]
                        accounts = vtb['accounts']
                        for account in accounts:
                            if account['platform'] == 'bilibili':
                                bili_id = account['id']
                                if bili_id not in config['ban_list']:
                                    await get_dyn(bili_id, last_time, browser, name, config)
                                    time.sleep(10)
            else:
                time.sleep(10)
        except KeyboardInterrupt:
            browser.close()

if __name__ == '__main__':
    asyncio.run(main())
