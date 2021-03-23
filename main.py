import asyncio
import json
import logging
import os
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
import requests
from pyppeteer import launch  # 不能删，隔壁 dynamic.py 还要调用的
from retrying import retry
from tinydb_dict import TinyDBDict

from dynamic import Dynamic
from utils import BiliAPI

import nest_asyncio
nest_asyncio.apply()

def get_vdb_list():
    vdb_list_url = "https://vdb.vtbs.moe/json/list.json"
    vdb_list = None
    try:
        vdb_list = requests.get(vdb_list_url).json()
    except Exception:
        vdb_list = None
    return vdb_list


def content_filter(content, filter_list):
    for f in filter_list:
        if content.find(f) != -1:
            return True
    return False

@retry(stop_max_attempt_number=5, wait_random_min=5000, wait_random_max=10000)
async def get_dyn(uid, last_time, browser, default_name, config, file_list):
    api = BiliAPI()
    dynamics = (api.get_dynamic(uid)).get('cards', [])
    if len(dynamics) == 0:  # 没有发过动态或者动态全删的直接结束
        return

    if uid not in last_time:  # 没有爬取过这位主播就把最新一条动态时间为 last_time
        dynamic = Dynamic(dynamics[0],
                          default_name, config['data_path'])
        if dynamic.time > datetime.now().timestamp() - timedelta(days=1).total_seconds():
            if dynamic.type not in config['exclude_types']:
                if not config['enable_filter'] or (config['enable_filter'] and content_filter(dynamic.content, config['content_filter'])):
                    await dynamic.get_screenshot(browser)
                    file_list.append(dynamic.img_path)
            last_time[uid] = dynamic.time
        else:
            last_time[uid] = int(datetime.now().timestamp())
        return

    for dynamic in dynamics[::-1]:  # 从旧到新取最近5条动态
        dynamic = Dynamic(dynamic, default_name, config['data_path'])
        if dynamic.time > last_time[uid]:
            if dynamic.type not in config['exclude_types']:
                if not config['enable_filter'] or (config['enable_filter'] and content_filter(dynamic.content, config['content_filter'])):
                    await dynamic.get_screenshot(browser)
                    file_list.append(dynamic.img_path)
            last_time[uid] = dynamic.time


def dd_b64(param):
    """
    对邮件header及附件的文件名进行两次base64编码，防止outlook中乱码。
    email库源码中先对邮件进行一次base64解码然后组装邮件
    :param param: 需要防止乱码的参数
    :return:
    """
    param = '=?utf-8?b?' + \
        base64.b64encode(param.encode('UTF-8')).decode() + '?='
    return param


@retry(stop_max_attempt_number=5, wait_random_min=5000, wait_random_max=10000)
def sendmail(sender, receiver, smtpserver, username, password, img_lists):
    now_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    mail_title = f'【DDDynamicRecorder自动邮件】{now_str}动态观测结果'

    # 创建一个带附件的实例
    message = MIMEMultipart()
    message['From'] = sender
    message['To'] = ";".join(receiver)
    message['Subject'] = Header(mail_title, 'utf-8')

    # 邮件正文内容
    message.attach(
        MIMEText(f'{now_str}动态观测结果，共记录到动态{len(img_lists)}条。\n', 'plain', 'utf-8'))

    for img_path in img_lists:
        att = MIMEText(open(img_path, 'rb').read(), 'base64', 'utf-8')
        att["Content-Type"] = 'application/octet-stream'
        att["Content-Disposition"] = f'attachment; filename="{dd_b64(os.path.basename(img_path))}"'
        message.attach(att)

    # 注意：如果遇到发送失败的情况（提示远程主机拒接连接），这里要使用SMTP_SSL方法
    smtpObj = smtplib.SMTP_SSL(host=smtpserver)
    smtpObj.connect(host=smtpserver, port=465)
    smtpObj.login(username, password)
    smtpObj.sendmail(sender, receiver, message.as_string())
    logging.info("邮件发送成功！")
    smtpObj.quit()


async def runner(config, config_path, vtb_details, last_time, file_list):
    browser = await launch(args=['--no-sandbox'])
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
                    await get_dyn(bili_id, last_time, browser, name, config, file_list)
                    await asyncio.sleep(10)
    await browser.close()


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

    file_list = []
    while True:
        new_list = get_vdb_list()
        if new_list:
            vtb_list = new_list
            if "vtbs" in vtb_list:
                vtb_details = vtb_list['vtbs']
                await runner(config, config_path, vtb_details, last_time, file_list)
                if config.get("email", {}).get("enable", False):
                    mail_config = config.get("email", {})
                    sendmail(mail_config.get("sender", ""), mail_config.get("receiver", []), mail_config.get(
                        "smtpserver", ""), mail_config.get("username", ""), mail_config.get("password", ""), file_list)
                    if not mail_config.get("keep_images_after_sent", True):
                        for ip in file_list:
                            os.remove(ip)
                file_list.clear()
                
        else:
            time.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
