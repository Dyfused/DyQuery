from nonebot import logger
from nonebot import on_command
from nonebot import get_plugin_config

from nonebot_plugin_orm import async_scoped_session
from nonebot.exception import FinishedException
from nonebot.adapters import Event
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.adapters import Message, Bot

from nonebot.adapters.discord import MessageSegment as DiscordMessageSegment

from nonebot.params import CommandArg


from nonebot.adapters.discord.api import (
    StringOption,
)
from nonebot.adapters.discord.commands import (
    CommandOption,
    on_slash_command,
)

from .config import Config
from .dyuserinfo import dyUserInfo

import asyncio
from typing import Optional

from .utils import *
from .b20utils import wrapper_draw_best_20,wrapper_draw_best_20_binary

config = get_plugin_config(Config)
rule = Rule(is_enabled, is_whitelist,is_whitelist_b20)

# =============Normal matchers=============
best20 = on_command("dyb20", rule=rule, aliases={"b20"}, priority=10, block=True)
# =============Discord matchers=============
best20_discord = on_slash_command(
    name="b20",
    description="Get detailed Best20 for user",
    options=[
        StringOption(
            name="username",
            description="The other user you want to query. Leave to none if you want to query your best20.",
            required=False
        )
    ],
    rule=rule,
    priority=5
)

# =============Normal handlers=============
@best20.handle()
async def handle_dynamite_b20_command(bot: Bot, event: Event, sql_session:async_scoped_session,arg: Message = CommandArg()) -> None:
    """
    Author: yuhao7370
    This part is taken from yuhao7370's b20 handler, and is adapted to work in AXIS5's bot.
    """
    qqid = str(event.user_id)
    args = [item for item in str(arg).strip().split() if item]

    try:
        if len(args) == 1:
            # query other user's best20
            username = args[0]
            uuid,placeholder=await fetch_user(username)
            # raise BombException if user doesn't exist
            
        else:
            # query the linked user's best20
            if(dyuserinfo := await sql_session.get(dyUserInfo, event.get_user_id())):
                username=dyuserinfo.dynamite_username
                uuid=dyuserinfo.dynamite_user_id
            else:
                await best20.finish("您还未绑定Dynamite用户名。请使用 /dybind <用户名> 来绑定。", reply_message=True)

        await best20.send(f"正在查询 {username} 的 Best20 成绩", reply_message=True)
        image_b64 = await wrapper_draw_best_20(
            uuid,
            username,
            timeout_seconds= max(20, config.http_timeout_seconds * 3)
        )
        await best20.finish(MessageSegment.image(image_b64), reply_message=True)
    except asyncio.TimeoutError:
        await best20.finish("查询超时，请稍后重试", reply_message=True)
    except BombException as exc:
        logger.exception(f"Dynamite b20 failed: {exc}")
        await best20.finish("查询失败: 500 USER_NOT_FOUND: User does not exist.", reply_message=True)
    except FinishedException:
        raise
    except Exception as exc:
        logger.exception(f"Dynamite b20 failed: {exc}")
        await best20.finish("查询失败, 请稍后再试", reply_message=True)

# =============Discord handlers=============
@best20_discord.handle()
async def handle_best20_discord(bot: Bot, event: Event, sql_session:async_scoped_session,username:CommandOption[Optional[str]]):
    """
    Author: yuhao7370, AXIS5
    Discord adaptions.
    """
    await best20_discord.send_deferred_response()

    discord_id = str(event.get_user_id())
    usr=username
    
    try:
        if usr is not None:
            # query other user's best20
            usr=usr.strip()
            logger.debug(f"get user name: {usr}")
            uuid,placeholder=await fetch_user(usr)
            # raise BombException if user doesn't exist
        else:
            # query the linked user's best20
            if(dyuserinfo := await sql_session.get(dyUserInfo, discord_id)):
                usr=dyuserinfo.dynamite_username
                uuid=dyuserinfo.dynamite_user_id
            else:
                await best20_discord.finish("\nYour Discord account has not linked with any Dynamite Explode accounts yet. Use /dybind <username> to link with one.")

        await best20_discord.send(f"Getting Best20 scores for {usr}")
        # Generate image directly. Discord does not support base64 strings for images
        image_data = await wrapper_draw_best_20_binary(
            uuid,
            usr,
            timeout_seconds= max(20, config.http_timeout_seconds * 3)
        )
        with BytesIO() as bytes_io:
            # image_jpg=image_data.convert("RGB")
            image_data.save(bytes_io, "PNG")
            raw = bytes_io.getvalue()
        await best20_discord.finish(DiscordMessageSegment.attachment(file="image.jpg",content=raw))
    except asyncio.TimeoutError:
        await best20_discord.finish("Query failed: Timeout. Please try again later.")
    except BombException as exc:
        logger.exception(f"Dynamite b20 failed: {exc}")
        await best20_discord.finish("Query failed: 500 USER_NOT_FOUND: User does not exist.")
    except FinishedException:
        raise
    except Exception as exc:
        logger.exception(f"Dynamite b20 failed: {exc}")
        await best20_discord.finish("Query failed, please try again later.")