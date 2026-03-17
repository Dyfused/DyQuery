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

diffs=["CASUAL","NORMAL","HARD","MEGA","GIGA","TERA"]


# =============Normal matchers=============
bind = on_command("dybind", rule=rule, aliases={"绑定用户"}, priority=10, block=True)
query_recent = on_command("recent", rule=rule, aliases={"最近成绩"}, priority=10, block=True)
# =============Discord matchers=============
bind_discord = on_slash_command(
    name="dybind",
    description="Calculate R.Point for Dynamite",
    options=[
        StringOption(name="usr",description="Dynamite Explode User Name",required=True)
    ],
    rule=rule,
    priority=5
)

query_recent_discord = on_slash_command(
    name="recent",
    description="Get the latest play record for Dynamite",
    rule=rule,
    priority=5
)

query_recent_discord_text=on_slash_command(
    name="recent-text",
    description="Get the latest play record for Dynamite in text format",
    rule=rule,
    priority=5
)

# ===============Account Bind================

@bind.handle()
async def handle_bind(bot:Bot, event: Event, args: Message = CommandArg()):

    # get arguments
    args = args.extract_plain_text().strip()
    # logger.debug(f"current bot info:{bot}")

    account_user_id=event.get_user_id()
    if bot.type=="Discord":
        reply = DiscordMessageSegment.mention_user(account_user_id)
        # reply = DiscordMessageSegment.reply(event.message_id)
        if not args:
            await bind.finish(reply + "\nPlease provide your Dynamite Explode user name.\nUsage：/dybind <username>")
    else:
        reply = MessageSegment.reply(event.message_id)
        if not args:
            await bind.finish(reply + "请提供要绑定的Dynamite Explode用户名。\n使用方法：/dybind <用户名> 或 /绑定用户 <用户名>")
    
    try:
        if bot.type=="Discord":
            rp_text=await bind_user(account_user_id,args,"Discord")
            logger.debug(f"Received bind command with args: {args} from Discord user: {account_user_id}")
        else:
            rp_text=await bind_user(account_user_id,args)
            logger.debug(f"Received bind command with args: {args} from QQ user: {account_user_id}")
    except Exception as exc:
        logger.info("USER_NOT_FOUND:用户不存在")
        # logger.debug(f"Received error response from user search endpoint: {exc}")
        await bind.finish(reply +"\n500 USER_NOT_FOUND: User does not exist.")
    await bind.finish(reply + rp_text)

# ===============Recent Query================
    
@query_recent.handle()
async def handle_query_recent(bot:Bot, event: Event, sql_session:async_scoped_session,args: Message = CommandArg()):

    args = args.extract_plain_text().strip().lower()
    # logger.debug(f"current bot info:{bot}")
    
    if bot.type=="Discord":
        # Discord bot
        reply = DiscordMessageSegment.mention_user(event.user_id)
    else:
        reply = MessageSegment.reply(event.message_id)

    # output
    if args!="text" and args!="":
        if bot.type=="Discord":
            await query_recent.finish(reply + f"\nWrong argument format. Use /recent or /recent text to get your latest play record.\n/recent :Get the record image.\n/recent text :Get the record in text format.")
        else:
            await query_recent.finish(f"参数错误，请使用 /recent 或 /recent text 来查询最近游玩记录\n/recent 查询带图片的记录\n/recent text 查询文本记录")
        return
    
    if (dyuserinfo := await sql_session.get(dyUserInfo, event.get_user_id())):
        # query recent play record

        if bot.type=="Discord":
            await query_recent.send(DiscordMessageSegment.text(f"Getting the latest play record for user: {dyuserinfo.dynamite_username}"))
        else:
            await query_recent.send(reply + f"正在查询{dyuserinfo.dynamite_username}的最近游玩记录")
        
        # fetch recent record
        try:
            r, music_name, difficulty_class, difficulty_value, score, perfect, good, miss, playtime, set_id, accuracy,user_name = await fetch_recent(dyuserinfo)

        except Exception as exc:
            logger.error("Query Failed")
            # logger.debug(f"Received error response from user search endpoint: {exc}")
            await query_recent.finish(reply +"Query Failed")
        
        if args=="text":
            # output recent record in text
            if bot.type=="Discord":
                await query_recent.finish(reply+ f"\n{user_name}\'s latest play record: \nMusic name: {music_name}\nDifficulty: {diffs[difficulty_class-1]} {difficulty_value}\nScore: {score}\nPerfect: {perfect}\nGood: {good}\nMiss: {miss}\nR.Points: {r}\nAccuracy: {accuracy*100:.2f}%\nData come from Dynamite Explode")
            else:
                await query_recent.finish(f"玩家{user_name}的最近游玩记录：\n曲名：{music_name}\n难度：{diffs[difficulty_class-1]} {difficulty_value}\n分数：{score}\nPerfect: {perfect}\nGood: {good}\nMiss: {miss}\nR值：{r}\n准确率：{accuracy*100:.2f}%\n数据来源: Dynamite Explode")
        elif args=="":
            # generate recent image
            recent_image = await generate_image_recent(
                r=r,
                music_name=music_name,
                difficulty_class=difficulty_class,
                difficulty_value=difficulty_value,
                score=score,
                perfect=perfect,
                good=good,
                miss=miss,
                playtime=playtime,
                set_id=set_id,
                accuracy = accuracy,
                user_name=  user_name
            )

            temp_filename=generate_temp_filename()
            cache_file =store.get_plugin_cache_file(temp_filename)
            recent_image.save(cache_file,format="PNG")

            try:
                if bot.type=="Discord":
                    with cache_file.open("rb") as fi:
                        await query_recent.send(reply + DiscordMessageSegment.attachment(file=cache_file.name,content=fi.read()))
                else:
                    await query_recent.send(reply + MessageSegment.image(cache_file))
            except Exception as e:
                logger.error(f"发送图片失败: {e}")
            finally:
                # 异步清理临时文件
                asyncio.create_task(cleanup_temp_file(cache_file))

    else:
        # no existing record
        if bot.type=="Discord":
            await query_recent.finish(reply + "\nYour Discord account has not linked with any Dynamite Explode accounts yet. Use /dybind <username> to link with one.")
        else:
            await query_recent.finish(reply + "您还未绑定Dynamite用户名。请使用 /dybind <用户名> 来绑定。")

# ================Discord Handlers===============

"""
async def _(event:InteractionCreateEvent,usr: CommandOption[str]):
    discord_user=event.get_user_id()
    await asyncio.sleep(2)
    await bind_discord.send(DiscordMessageSegment.text(f"Received username: {usr}"))
"""

@bind_discord.handle()
async def handle_bind_discord(event:InteractionCreateEvent,usr: CommandOption[str]):
    await bind_discord.send_deferred_response()
    discord_user=event.get_user_id()
    logger.debug(f"handling bind, argument: {usr}")
    try:
        rp_text=await bind_user(discord_user,usr,"Discord")
    except Exception as exc:
        logger.info("USER_NOT_FOUND:用户不存在")
        # logger.debug(f"Received error response from user search endpoint: {exc}")
        await bind_discord.finish(DiscordMessageSegment.text("500 USER_NOT_FOUND: User does not exist."))
    await bind_discord.finish(DiscordMessageSegment.text(rp_text))


@query_recent_discord.handle()
async def handle_discord_recent(event:InteractionCreateEvent,sql_session:async_scoped_session):
    await query_recent_discord.send_deferred_response()
    user=event.get_user_id()
    reply = DiscordMessageSegment.mention_user(user)

    if (dyuserinfo := await sql_session.get(dyUserInfo, user)):
        await query_recent_discord.send_response(DiscordMessageSegment.text(f"Getting the latest play record for user: {dyuserinfo.dynamite_username}"))
    else:
        await query_recent_discord.finish("\nYour Discord account has not linked with any Dynamite Explode accounts yet. Use /dybind <username> to link with one.")
    # fetch recent record
    try:
        r, music_name, difficulty_class, difficulty_value, score, perfect, good, miss, playtime, set_id, accuracy,user_name = await fetch_recent(dyuserinfo)
    except Exception as exc:
        logger.error("Query Failed")
        # logger.debug(f"Received error response from user search endpoint: {exc}")
        await query_recent_discord.finish(reply +"Query Failed")

    # generate recent image
    recent_image = await generate_image_recent(
        r=r,
        music_name=music_name,
        difficulty_class=difficulty_class,
        difficulty_value=difficulty_value,
        score=score,
        perfect=perfect,
        good=good,
        miss=miss,
        playtime=playtime,
        set_id=set_id,
        accuracy = accuracy,
        user_name=  user_name
    )
    temp_filename=generate_temp_filename()
    cache_file = store.get_plugin_cache_file(temp_filename)
    recent_image.save(cache_file,format="PNG")
    try:  
        with cache_file.open("rb") as fi:
            await query_recent_discord.send_followup_msg(reply + DiscordMessageSegment.attachment(file=cache_file.name,content=fi.read()))
    except Exception as e:
        logger.error(f"发送图片失败: {e}")
    finally:
        # 异步清理临时文件
        asyncio.create_task(cleanup_temp_file(cache_file))


@query_recent_discord_text.handle()
async def handle_discord_recent_text(event:InteractionCreateEvent,sql_session:async_scoped_session):
    await query_recent_discord_text.send_deferred_response()
    user=event.get_user_id()
    reply = DiscordMessageSegment.mention_user(user)
    
    if (dyuserinfo := await sql_session.get(dyUserInfo, user)):
        await query_recent_discord_text.send_response(DiscordMessageSegment.text(f"Getting the latest play record for user: {dyuserinfo.dynamite_username}"))

    else:
        await query_recent_discord_text.finish("\nYour Discord account has not linked with any Dynamite Explode accounts yet. Use /dybind <username> to link with one.")
    # fetch recent record
    try:
        r, music_name, difficulty_class, difficulty_value, score, perfect, good, miss, playtime, set_id, accuracy,user_name = await fetch_recent(dyuserinfo)

    except Exception as exc:
        logger.error("Query Failed")
        # logger.debug(f"Received error response from user search endpoint: {exc}")
        await query_recent_discord_text.finish(reply +"Query Failed")

    await query_recent_discord_text.finish(reply+ f"\n{user_name}\'s latest play record: \nMusic name: {music_name}\nDifficulty: {diffs[difficulty_class-1]} {difficulty_value}\nScore: {score}\nPerfect: {perfect}\nGood: {good}\nMiss: {miss}\nR.Points: {r}\nAccuracy: {accuracy*100:.2f}%\nData come from Dynamite Explode")
