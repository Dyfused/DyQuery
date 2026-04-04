from pathlib import Path
from nonebot import get_plugin_config
from nonebot import logger

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import httpx
from httpx import AsyncHTTPTransport  # 导入 Transport 模块

import time
import random
import asyncio
from datetime import datetime
import pytz

from io import BytesIO

from nonebot.adapters.onebot.v11 import PrivateMessageEvent, GroupMessageEvent
from nonebot.adapters import Bot

from nonebot.adapters.discord import (
    GuildMessageCreateEvent,
    ApplicationCommandInteractionEvent,
)
from nonebot.adapters import Event

from nonebot_plugin_orm import get_session

from .config import Config
from .dyuserinfo import dyUserInfo

config = get_plugin_config(Config)


class BombException(RuntimeError):
    """
    Explode Errors
    """

    pass


image_asset_dir = Path(__file__).parent / "assets"
image_asset_dir.mkdir(exist_ok=True)

# httpx retry config
transport = AsyncHTTPTransport(retries=config.http_retry_times)


# =============Rule Checkers=============
async def is_enabled() -> bool:
    return config.dyquery_plugin_enabled


async def is_whitelist(bot: Bot, event: Event) -> bool:
    # check_type=type(event.group_id)
    # logger.debug(f"Group type:{check_type}")
    logger.debug(f"Getting bot info:{bot}")

    if isinstance(event, GroupMessageEvent):

        return str(event.group_id) in config.dyquery_white_list
        # logger.debug(f"Checking value {rtn}")
    elif isinstance(event, GuildMessageCreateEvent):
        logger.debug(f"Get message:{event.message} from guild {event.guild_id}")
        return True
    elif isinstance(event, ApplicationCommandInteractionEvent):
        logger.debug(f"Get message:{event.data} from guild {event.guild_id}")
        return True
    elif isinstance(event, PrivateMessageEvent):
        return True
    else:
        return False


async def is_whitelist_b20(bot: Bot, event: Event) -> bool:
    # check_type=type(event.group_id)
    # logger.debug(f"Group type:{check_type}")
    logger.debug(f"Getting bot info:{bot}")

    if isinstance(event, GroupMessageEvent):
        return str(event.group_id) in config.dyquery_b20_white_list
        # logger.debug(f"Checking value {rtn}")
    elif isinstance(event, GuildMessageCreateEvent):
        logger.debug(f"Get message:{event.message} from guild {event.guild_id}")
        return True
    elif isinstance(event, ApplicationCommandInteractionEvent):
        logger.debug(f"Get message:{event.data} from guild {event.guild_id}")
        return True
    elif isinstance(event, PrivateMessageEvent):
        return True
    else:
        return False


# 计算准确率
def calculate_acc(perfect: int, good: int, miss: int) -> float:
    total = perfect + good + miss
    if total == 0:
        return 0.0
    return (perfect + good * 0.5) / total


def paste_rank(image: Image.Image, score: int):
    """
    returns a difficulty icon in Image.Image
    """
    rank_icon: Image.Image
    if score == 1000000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_0.png")
    elif score >= 980000 and score < 1000000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_1.png")
    elif score >= 950000 and score < 980000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_2.png")
    elif score >= 900000 and score < 950000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_3.png")
    elif score >= 800000 and score < 900000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_4.png")
    elif score >= 700000 and score < 800000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_5.png")
    elif score >= 600000 and score < 700000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_6.png")
    elif score >= 500000 and score < 600000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_7.png")
    elif score >= 400000 and score < 500000:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_8.png")
    else:
        rank_icon = Image.open(image_asset_dir / "UI1_Difficulties_9.png")
    rank_icon = rank_icon.resize((230, 230))
    image.paste(rank_icon, (110, 400), rank_icon)
    return image


async def fetch_user(user_name) -> tuple[str, str]:
    """
    Get explode user data by name
    return:id,username
    """
    try:
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.post(
                config.api_base_url + config.user_search_api,
                json={"username": user_name},
                headers={
                    "Accept": "application/json,text/plain",
                    "Content-Type": "application/json",
                },
                timeout=config.http_timeout_seconds,
            )
            resp.raise_for_status()
            # get the data field from the response, which should contain user info if the username exists
            data = resp.json().get("data", {})
    except httpx.TimeoutException as exc:
        # 原逻辑：超时/网络异常会进入 Exception 并被包装成 BombException
        # 现在：将「API 超时」统一转换为 asyncio.TimeoutError，便于上层用 except asyncio.TimeoutError 做提示
        logger.info(f"API timeout in fetch_user: {exc}")
        raise asyncio.TimeoutError("Explode API request timed out") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 500:
            logger.info("500 USER_NOT_FOUND: User does not exist")
            raise BombException("500 USER_NOT_FOUND: User does not exist")
        raise BombException(f"{exc.response.status_code}: other server error occured")
    except Exception as exc:
        logger.info(f"请求异常: {exc}")
        raise BombException(f"{exc}")

    # 原逻辑：直接 return data["id"], data["username"]，当 data 为空时会 KeyError
    # 按你的约定：用户不存在返回 500（这里也兜底处理为 USER_NOT_FOUND）
    if not isinstance(data, dict) or "id" not in data or "username" not in data:
        raise BombException("500 USER_NOT_FOUND: User does not exist")

    return str(data["id"]), str(data["username"])


async def fetch_user_by_id(user_id: str):
    """
    Get explode user data info by user id
    return:data in dict
    """
    try:
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get(
                config.api_base_url + config.user_base_api + user_id,
                headers={
                    "Accept": "application/json,text/plain",
                    "Content-Type": "application/json",
                },
                timeout=config.http_timeout_seconds,
            )
            resp.raise_for_status()
            # get the data field from the response, which should contain user info if the username exists
            data = resp.json().get("data", {})
    except httpx.TimeoutException as exc:
        # 原逻辑：超时会被包装为 BombException；现在统一转换为 asyncio.TimeoutError
        logger.info(f"API timeout in fetch_user_by_id: {exc}")
        raise asyncio.TimeoutError("Explode API request timed out")
    except httpx.HTTPStatusError as exc:
        # 按约定：用户不存在返回 500
        if exc.response.status_code == 500:
            raise BombException("500 USER_NOT_FOUND: User does not exist")
        raise BombException(f"{exc.response.status_code}: other server error occured")
    except Exception as exc:
        raise BombException(f"{exc}")

    return data


async def bind_user(user_id, user_name, source="QQ") -> str:
    """
    bind with dynamite account and return reply string
    """
    # verify that the provided username actually exists by calling
    # the configured search endpoint.
    response = ""
    account_user_id = user_id
    try:
        id, name = await fetch_user(user_name)
    except asyncio.TimeoutError:
        # 原逻辑：所有异常都会被包装为 BombException
        # 现在：API 超时按约定向上抛 asyncio.TimeoutError，便于 handlers.py 做超时提示
        raise
    except BombException:
        # 原逻辑：这里会被 except Exception 包住重新包装；现在保持原异常信息
        raise
    except Exception as exc:
        raise BombException(f"{exc}")

    sql_session = get_session()
    async with sql_session.begin():
        if source == "Discord":
            # For Discord bots
            if dyuserinfo := await sql_session.get(dyUserInfo, account_user_id):
                previous_username = dyuserinfo.dynamite_username
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(id)
                dyuserinfo.source = "Discord"
                sql_session.add(dyuserinfo)
                response = f"\nLinked with Explode user: {name}\nPreviously linked username: {previous_username}"

                # await bind.send(reply + f"\nLinked with Explode user: {data['username']}\nPreviously linked username: {previous_username}")
            else:
                # no existing record for this user, create a new one
                dyuserinfo = dyUserInfo(account_user_id)
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(id)
                dyuserinfo.source = "Discord"
                sql_session.add(dyuserinfo)
                response = f"\nLinked with Explode user: {name}"
                # await bind.send(reply + f"\nLinked with Explode user: {data['username']}")
        else:
            if dyuserinfo := await sql_session.get(dyUserInfo, account_user_id):
                previous_username = dyuserinfo.dynamite_username
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(id)
                sql_session.add(dyuserinfo)
                response = f"已绑定Explode用户：{name}\n旧用户名：{previous_username}"
                # await bind.send(reply + f"已绑定Explode用户：{data['username']}\n旧用户名：{previous_username}")
            else:
                # no existing record for this user, create a new one
                dyuserinfo = dyUserInfo(account_user_id)
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(id)
                sql_session.add(dyuserinfo)
                response = f"已绑定Explode用户：{name}"
                # await bind.send(reply + f"已绑定Explode用户：{data['username']}")
    return response


# fetch recent record
async def fetch_recent(dyuserinfo: dyUserInfo):
    """
    Fetch the recent record of a user
    """
    try:
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get(
                config.api_base_url
                + config.user_base_api
                + dyuserinfo.dynamite_user_id
                + "/last",
                headers={
                    "Accept": "application/json,text/plain",
                    "Content-Type": "application/json",
                },
                timeout=config.http_timeout_seconds,
            )
            resp.raise_for_status()

            payload = resp.json()
            data = payload.get("data")

            # 原逻辑：len(resp.json().get("data", []))==0 时 raise 字符串（会触发 TypeError）
            # 现在：无游玩记录时抛 BombException，交给上层做提示
            # 说明：你提到「无游玩记录并不会导致返回 json 为空」，因此这里不判断 payload 是否为空，
            # 仅判断 data 是否为空/空列表/不可解析。
            if data is None:
                raise BombException("NO_PLAY_RECORD: User has no play record")
            if isinstance(data, list):
                if len(data) == 0:
                    raise BombException("NO_PLAY_RECORD: User has no play record")
                latest_record = data[0]
            else:
                # 兼容后端如果返回单个 dict 的情况
                if not isinstance(data, dict) or len(data) == 0:
                    raise BombException("NO_PLAY_RECORD: User has no play record")
                latest_record = data
    except httpx.TimeoutException as exc:
        # 原逻辑：超时会被包装为 BombException；现在统一转换为 asyncio.TimeoutError
        logger.info(f"API timeout in fetch_recent: {exc}")
        raise asyncio.TimeoutError("Bomb API request timed out")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 500:
            raise BombException("500 USER_NOT_FOUND: User does not exist")
        raise BombException(f"{exc.response.status_code}: other server error occured")
    except BombException:
        raise
    except Exception as exc:
        raise BombException(f"{exc}")

    logger.debug(f"Received latest record: {latest_record}")

    # recent play record
    set_info = latest_record.get("set_info", {})
    chart_info = latest_record.get("chart_info", {})
    r = latest_record.get("r", "UnRanked")
    music_name = set_info.get("music_name")
    difficulty_class = chart_info.get("difficulty_class")
    difficulty_value = chart_info.get("difficulty_value")
    score = latest_record.get("score")
    perfect = latest_record.get("perfect")
    good = latest_record.get("good")
    miss = latest_record.get("miss")
    playtime = latest_record.get("upload_time")
    playtime = datetime.fromisoformat(playtime)

    if dyuserinfo.source == "Discord":
        playtime = playtime.astimezone(pytz.timezone("UTC")).strftime(
            "%Y-%m-%d %H:%M:%S %Z %z"
        )
    else:
        playtime = playtime.astimezone(pytz.timezone("Asia/Shanghai")).strftime(
            "%Y-%m-%d %H:%M:%S %Z %z"
        )
    set_id = latest_record.get("set_id")
    accuracy = calculate_acc(perfect, good, miss)
    user_name = dyuserinfo.dynamite_username

    return (
        r,
        music_name,
        difficulty_class,
        difficulty_value,
        score,
        perfect,
        good,
        miss,
        playtime,
        set_id,
        accuracy,
        user_name,
    )


async def fetch_b20(uuid: str):
    """
    Fetch the Best20 record of a user
    """
    try:
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get(
                config.api_base_url + config.user_base_api + uuid + "/best",
                headers={
                    "Accept": "application/json,text/plain",
                    "Content-Type": "application/json",
                },
                timeout=config.http_timeout_seconds,
            )
            resp.raise_for_status()

            payload = resp.json()
            best_records = payload.get("data")

            # 原逻辑：默认 get("data", [])，但当后端返回 None/空时，后续绘图可能会崩
            # 现在：无游玩记录时抛 BombException，交给上层做提示
            if best_records is None:
                raise BombException("NO_PLAY_RECORD: User has no play record")
            if isinstance(best_records, list) and len(best_records) == 0:
                raise BombException("NO_PLAY_RECORD: User has no play record")
    except httpx.TimeoutException as exc:
        logger.info(f"API timeout in fetch_b20: {exc}")
        raise asyncio.TimeoutError() from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 500:
            raise BombException("500 USER_NOT_FOUND: User does not exist")
        raise BombException(f"{exc.response.status_code}: other server error occured")
    except BombException:
        raise
    except Exception as exc:
        raise BombException(f"{exc}")

    logger.debug(f"Received Best record: {best_records}")
    return best_records


async def generate_image_recent(**kwargs):
    """
    draw recent record image
    """
    r = kwargs.get("r", "UnRanked")
    music_name = kwargs.get("music_name")
    difficulty_class = kwargs.get("difficulty_class")
    difficulty_value = kwargs.get("difficulty_value")
    score = kwargs.get("score")
    perfect = kwargs.get("perfect")
    good = kwargs.get("good")
    miss = kwargs.get("miss")
    playtime = kwargs.get("playtime")

    set_id = kwargs.get("set_id")
    accuracy = kwargs.get("accuracy")
    user_name = kwargs.get("user_name")

    # in image format

    bg_file = image_asset_dir / "bg.png"
    bg_asset_file = image_asset_dir / "bgfront2.png"
    new_image = Image.open(bg_file).convert("RGB")
    assets = Image.open(bg_asset_file)
    Logo = Image.open(image_asset_dir / "Logo.png").convert("RGBA")
    # Logo = Logo.resize((200,256))

    # rounded rectangle mask for background image
    image_mask = Image.new("L", (1900, 830), 0)
    draw_mask = ImageDraw.Draw(image_mask)
    draw_mask.rounded_rectangle((0, 0, 1900, 830), 70, fill=255)

    bg_image: Image.Image

    try:
        # There are redirects in the bg download url, so we need to allow redirects in the http client
        async with httpx.AsyncClient(
            transport=transport, follow_redirects=True
        ) as client:
            bg_response = await client.get(
                config.bg_download_url_base + str(set_id),
                timeout=config.http_timeout_seconds,
            )
            bg_response.raise_for_status()
            bg_image = Image.open(BytesIO(bg_response.content)).convert("RGBA")
            bg_image = bg_image.resize((1900, 830))
    except Exception as e:
        logger.warning(f"Failed to download background image: {e}")
        bg_image = Image.new("RGBA", (1900, 830), (50, 50, 50, 255))

    bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=10))

    new_image.paste(bg_image, (50, 200), image_mask)
    new_image.paste(Logo, (40, 15), Logo)

    new_image.paste(assets, (0, 0), assets)

    # rank icon
    new_image = paste_rank(new_image, int(score))

    draw = ImageDraw.Draw(new_image)
    # load fonts
    eurostyle = ImageFont.truetype(str(image_asset_dir / "EuroStyle Normal.ttf"), 100)
    eurostyle_bold = ImageFont.truetype(str(image_asset_dir / "EurostileBold.ttf"), 100)
    eurostyle_italic = ImageFont.truetype(
        str(image_asset_dir / "EurostileOblique.ttf"), 160
    )
    eurostyle_italic_small = ImageFont.truetype(
        str(image_asset_dir / "EurostileOblique.ttf"), 50
    )
    title = ImageFont.truetype(str(image_asset_dir / "SourceHanSansCN-Medium.otf"), 100)
    title_small = ImageFont.truetype(
        str(image_asset_dir / "SourceHanSansCN-Medium.otf"), 55
    )
    player_info_font = ImageFont.truetype(
        str(image_asset_dir / "SourceHanSansCN-Medium.otf"), 70
    )
    saira_small = ImageFont.truetype(str(image_asset_dir / "Saira-Regular.ttf"), 75)
    saira_time = ImageFont.truetype(str(image_asset_dir / "Saira-Regular.ttf"), 50)
    saira_score = ImageFont.truetype(str(image_asset_dir / "Saira-Regular.ttf"), 140)

    draw.text((270, 50), "Recent Record", font=eurostyle_italic, fill=(255, 255, 255))

    # difficulty icon
    match (difficulty_class - 1):
        case 0:
            draw.circle((200, 300), 75, fill=(56, 142, 60))
        case 1:
            draw.circle((200, 300), 75, fill=(0, 145, 234))
        case 2:
            draw.circle((200, 300), 75, fill=(244, 67, 54))
        case 3:
            draw.circle((200, 300), 75, fill=(106, 27, 154))
        case 4:
            draw.circle((200, 300), 75, fill=(170, 170, 170))
        case 5:
            draw.circle((200, 300), 75, fill=(0, 0, 0))
    # title text box
    temp_image = Image.new("RGB", (1, 1), (0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_image)
    bbox = temp_draw.textbbox((0, 0), f"{music_name}", title, anchor="lt", stroke_width=3)

    # this is the text_width
    text_width = bbox[2] - bbox[0]

    # draw text
    draw.text(
        (200, 256),
        f"{difficulty_value}",
        font=eurostyle_bold,
        fill=(255, 255, 255),
        anchor="ma",
        align="center",
    )
    # Music name
    if text_width <= 1650:
        draw.text(
            (300, 290),
            f"{music_name}",
            font=title,
            fill=(0, 0, 0),
            anchor="lm",
            stroke_width=3,
            stroke_fill=(255, 255, 255),
        )
    else:
        tlen = len(music_name)
        logger.debug(f"Title length:{tlen}")
        # music_name=music_name[:60]+"\n"+music_name[61:]
        draw.text(
            (300, 270),
            f"{music_name}",
            font=title_small,
            fill=(0, 0, 0),
            stroke_width=2,
            stroke_fill=(255, 255, 255),
        )
    # score
    draw.text(
        (800, 400),
        f"{score}",
        font=saira_score,
        fill=(255, 255, 255),
        anchor="ma",
        align="center",
    )
    # player
    draw.text(
        (430, 630),
        "Player:",
        align="center",
        anchor="ma",
        font=saira_small,
        fill=(255, 255, 255),
    )
    draw.text(
        (430, 740),
        f"{user_name}",
        align="center",
        anchor="ma",
        font=player_info_font,
        fill=(255, 255, 255),
    )
    # R points
    draw.text(
        (1025, 630),
        f"R.Points:\n{r}",
        align="center",
        anchor="ma",
        font=saira_small,
        fill=(255, 255, 255),
    )
    draw.text(
        (700, 860),
        f"Acc: {accuracy*100:.2f}%",
        align="center",
        anchor="ma",
        font=saira_small,
        fill=(255, 255, 255),
    )
    # play details
    draw.text((1340, 435), "Perfect", font=saira_small, fill=(255, 255, 255))
    draw.text((1340, 645), "Good", font=saira_small, fill=(255, 255, 255))
    draw.text((1340, 855), "Miss", font=saira_small, fill=(255, 255, 255))
    draw.text(
        (1870, 435), f"{perfect}", anchor="ra", font=saira_small, fill=(255, 255, 255)
    )
    draw.text((1870, 645), f"{good}", anchor="ra", font=saira_small, fill=(255, 255, 255))
    draw.text((1870, 855), f"{miss}", anchor="ra", font=saira_small, fill=(255, 255, 255))
    # play time
    draw.text((30, 1050), f"Played at: {playtime}", font=saira_time, fill=(255, 255, 255))
    # signature
    draw.text(
        (1950, 1050),
        "Code by AXIS5",
        anchor="ra",
        font=saira_time,
        fill=(255, 255, 255),
    )
    return new_image


def generate_temp_filename() -> str:
    """生成唯一的临时文件名"""
    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(1000, 9999)
    return f"processed_{timestamp}_{random_suffix}.png"


async def cleanup_temp_file(file_path: Path, delay: float = 10.0):
    """清理临时文件"""
    await asyncio.sleep(delay)
    try:
        if file_path.exists():
            logger.debug(f"Cleaning up temp pic: {file_path}")
            file_path.unlink()
    except Exception:
        pass
