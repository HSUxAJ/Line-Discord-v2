import os
import sys
from argparse import ArgumentParser
from dotenv import load_dotenv

import asyncio
import aiohttp
from aiohttp import web

import logging

from aiohttp.web_runner import TCPSite

from linebot import (
    AsyncLineBotApi, WebhookParser
)
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import multiprocessing
import DiscordBot
import requests
import json

# get channel_secret and channel_access_token from your environment variable
load_dotenv()
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

class Handler:
    def __init__(self, line_bot_api, parser):
        self.line_bot_api = line_bot_api
        self.parser = parser
        with open('data.json', 'r', encoding='utf-8') as f:
            self.discord_info = json.load(f)
        

    async def callback(self, request):
        signature = request.headers['X-Line-Signature']
        body = await request.text()

        try:
            events = self.parser.parse(body, signature)
        except InvalidSignatureError:
            return web.Response(status=400, text='Invalid signature')

        for event in events:
            if not isinstance(event, MessageEvent):
                continue
            if not isinstance(event.message, TextMessage):
                continue

            content_message = event.message.text
            await self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=content_message)
            )

            if event.source.type != 'group':
                return
            group_id = event.source.group_id
            user_id = event.source.user_id
            group_summary = await self.line_bot_api.get_group_summary(group_id)
            group_name = group_summary.group_name

            if group_id not in self.discord_info:
                print(group_name)
                new_info = self.create_discord_channel(line_group_id=group_id, group_name=group_name)
                self.discord_info.update(new_info)
                self.update_data(self.discord_info)
            
            
            profile = await self.line_bot_api.get_group_member_profile(group_id, user_id)
        
            headers = {
                "content-type": "application/json; charset=UTF-8",
                "Authorization": "Bearer {}".format(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
            }
            url = 'https://api.line.me/v2/bot/group/' + group_id + '/summary'

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response_json = await response.json()

            request_data = {
                "content": content_message,
                "username": profile.display_name,
                "avatar_url": profile.picture_url
            }

            # request_data = await Handler.create_request_data(self.line_bot_api, group_id, user_id, event.message.text)
            requests.post(url=self.discord_info[group_id]['webhook'], data=request_data)
                      
        return web.Response(text="OK\n")
    
    def update_data(self, info):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False)
    
    def create_discord_channel(self, line_group_id, group_name):
        discord_token = os.getenv('DISCORD_TOKEN', None)
        discord_guild_id = os.getenv('DISCORD_GUILD_ID', None)
        api_endpoint_channels = f'https://discord.com/api/v10/guilds/{discord_guild_id}/channels'

        headers = {
            'Authorization': f'Bot {discord_token}',
            'Content-Type': 'application/json',
        }

        # 創建文字頻道
        channel_data = {
            'name': group_name,  # 頻道名稱
            'type': 0,  # 文字頻道的類型
        }

        response_channel = requests.post(api_endpoint_channels, json=channel_data, headers=headers)
        if response_channel.status_code == 201:
            new_channel_data = response_channel.json()
            print(f'文字頻道 {new_channel_data["name"]} 已成功創建！')
        else:
            print('創建文字頻道時出現問題。')

        # 創建 Webhook
        API_ENDPOINT = f'https://discord.com/api/v10/channels/{new_channel_data["id"]}/webhooks'
        headers = {
            'Authorization': f'Bot {discord_token}',
            'Content-Type': 'application/json',
        }

        data = {
            'name': 'Webhook',  # Webhook 名稱
        }

        response = requests.post(API_ENDPOINT, json=data, headers=headers)
        if response.status_code == 200:
            new_webhook_data = response.json()
            print(f'Webhook 已成功創建，Webhook ID：{new_webhook_data["id"]}')
        else:
            print('創建 Webhook 時出現問題。')

        ret = {}
        ret[line_group_id] = {
            'name': group_name,
            'webhook': new_webhook_data["url"]
        }
        ret[new_channel_data["id"]] = {'line_group_id': line_group_id}
        return ret

    async def create_request_data(self, group_id, user_id, text=None):
        profile = await self.line_bot_api.get_group_member_profile(group_id, user_id)
        
        headers = {
            "content-type": "application/json; charset=UTF-8",
            "Authorization": "Bearer {}".format(os.environ['LINEBOT_ACCESS_TOKEN'])
        }
        url = 'https://api.line.me/v2/bot/group/' + group_id + '/summary'

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                await response.json()

        request_data = {
            "content": text,
            "username": profile.display_name,
            "avatar_url": profile.picture_url
        }
        return request_data

async def main(port=8080):
    session = aiohttp.ClientSession()
    async_http_client = AiohttpAsyncHttpClient(session)
    line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
    parser = WebhookParser(channel_secret)

    handler = Handler(line_bot_api, parser)

    app = web.Application()
    app.add_routes([web.post('/callback', handler.callback)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = TCPSite(runner=runner, port=port)
    await site.start()
    while True:
        await asyncio.sleep(3600)  # sleep forever


if __name__ == "__main__":
    p = multiprocessing.Process(target=DiscordBot.run_bot)
    p.start()
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=8080, help='port')
    options = arg_parser.parse_args()

    asyncio.run(main(options.port))