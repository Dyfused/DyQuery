from nonebot import logger
from nonebot import on_command
from nonebot import get_plugin_config

from nonebot_plugin_orm import async_scoped_session

from nonebot.adapters import Event
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import MessageSegment, PrivateMessageEvent,GroupMessageEvent
from nonebot.adapters import Message, Bot

from nonebot.adapters.discord import GuildMessageCreateEvent, InteractionCreateEvent,ApplicationCommandInteractionEvent
from nonebot.adapters.discord import MessageSegment as DiscordMessageSegment

from nonebot.params import CommandArg

import nonebot_plugin_localstore as store

from nonebot.adapters.discord.api import (
    IntegerOption,
    NumberOption,
    StringOption,
    SubCommandOption,
    User,
    UserOption,
)
from nonebot.adapters.discord.commands import (
    CommandOption,
    on_slash_command,
)

from .config import Config
from .dyuserinfo import dyUserInfo

import httpx
import asyncio

from .utils import *

config = get_plugin_config(Config)
rule = Rule(is_enabled, is_whitelist)

# =============Normal matchers=============
best20 = on_command("dyb20", rule=rule, aliases={"b20"}, priority=10, block=True)
# =============Discord matchers=============
best20_discord = on_slash_command(
    name="b20",
    description="Get detailed Best20 for user",
    rule=rule,
    priority=5
)
# =============Normal handlers=============
@best20.handle()
async def handle_best20(event:Event):
    pass

# =============Discord handlers=============
@best20.handle()
async def handle_best20_discord(event:Event):
    pass