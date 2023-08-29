import discord
from discord.ext import commands
import json
from linebot import LineBotApi, WebhookHandler
from linebot.models import *
import os
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.webhooks = True
intents.guilds = True
intents.webhooks = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

load_dotenv()
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None))
discord_token = os.getenv('DISCORD_TOKEN', None)
line_group_id = {}

@bot.event
async def on_message(message):
    if message.author.bot: return
    bot_send_message(message)

def bot_send_message(message):
	channel_id = str(message.channel.id)
	if channel_id not in line_group_id:
		update()
	print(line_group_id[channel_id]['line_group_id'])
	if message.attachments == []:
		line_bot_api.push_message(line_group_id[channel_id]['line_group_id'], TextSendMessage(text=message.content))
	else:
		image_url = str(message.attachments[0])
		image_message = ImageSendMessage(
			original_content_url=image_url,
			preview_image_url=image_url
			)
		line_bot_api.push_message(line_group_id[channel_id]['line_group_id'], image_message)
	
def update():
	global line_group_id
	with open('data.json', 'r', encoding='utf-8') as f:
	    line_group_id = json.load(f)

def run_bot():
    update()
    bot.run(discord_token)

if __name__ == '__main__':
    run_bot()