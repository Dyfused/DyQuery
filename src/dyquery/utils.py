from pathlib import Path
from nonebot import get_plugin_config
from nonebot import logger

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import httpx
import time
import random
import asyncio
from datetime import datetime
import pytz

from io import BytesIO

from nonebot.adapters.onebot.v11 import PrivateMessageEvent,GroupMessageEvent
from nonebot.adapters import Bot

from nonebot.adapters.discord import GuildMessageCreateEvent, InteractionCreateEvent,ApplicationCommandInteractionEvent
from nonebot.adapters import Event

from nonebot_plugin_orm import get_session

from .config import Config
from .dyuserinfo import dyUserInfo

config = get_plugin_config(Config)

image_asset_dir = Path(__file__).parent / "assets"
image_asset_dir.mkdir(exist_ok=True)

#=============Rule Checkers=============
async def is_enabled() -> bool:
    return config.dyquery_plugin_enabled

async def is_whitelist(bot:Bot,event: Event) -> bool:
    # check_type=type(event.group_id)
    # logger.debug(f"Group type:{check_type}")
    logger.debug(f"Getting bot info:{bot}")
    
    if(isinstance(event,GroupMessageEvent)):
        
        rtn = str(event.group_id) in config.dyquery_white_list
        # logger.debug(f"Checking value {rtn}")
        return rtn
    elif(isinstance(event,GuildMessageCreateEvent)):
        logger.debug(f"Get message:{event.message} from guild {event.guild_id}")
        return True
    elif(isinstance(event,ApplicationCommandInteractionEvent)):
        logger.debug(f"Get message:{event.data} from guild {event.guild_id}")
        return True
    elif(isinstance(event,PrivateMessageEvent)):
        return True
    else:
        return False

# 计算准确率
def calculate_acc(perfect: int, good: int, miss: int) -> float:
    total = perfect + good + miss
    if total == 0:
        return 0.0
    return (perfect + good * 0.5) / total

# 
def paste_rank(image:Image.Image ,score:int):
    """
    returns a difficulty icon in Image.Image
    """
    rank_icon: Image.Image
    if score==1000000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_0.png")
    elif score>=980000 and score<1000000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_1.png")
    elif score>=950000 and score<980000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_2.png")
    elif score>=900000 and score<950000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_3.png")
    elif score>=800000 and score<900000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_4.png")
    elif score>=700000 and score<800000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_5.png")
    elif score>=600000 and score<700000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_6.png")
    elif score>=500000 and score<600000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_7.png")
    elif score>=400000 and score<500000:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_8.png")
    else:
        rank_icon=Image.open(image_asset_dir / "UI1_Difficulties_9.png")
    rank_icon=rank_icon.resize((230,230))
    image.paste(rank_icon,(110,400),rank_icon)
    return image


async def bind_user(user_id,user_name,source="QQ") -> str: 
    """
    bind with dynamite account and return reply string
    """
    # verify that the provided username actually exists by calling
    # the configured search endpoint.
    response=""
    account_user_id=user_id
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                config.api_base_url + config.user_search_api,
                json={"username": user_name},
                headers={"Accept": "application/json,text/plain", "Content-Type": "application/json"},
                timeout=5,
            )
            resp.raise_for_status()
            # get the data field from the response, which should contain user info if the username exists
            data = resp.json().get("data", {})
    except Exception as exc:
        logger.info("USER_NOT_FOUND:用户不存在")
        raise exc
    
    sql_session=get_session()
    async with sql_session.begin():
        if source=="Discord":
        # For Discord bots
            if (dyuserinfo := await sql_session.get(dyUserInfo, account_user_id)):
                previous_username = dyuserinfo.dynamite_username
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(data["id"])
                dyuserinfo.source="Discord"
                sql_session.add(dyuserinfo)
                response=f"\nLinked with Explode user: {data['username']}\nPreviously linked username: {previous_username}"
                
                # await bind.send(reply + f"\nLinked with Explode user: {data['username']}\nPreviously linked username: {previous_username}")
            else:
                # no existing record for this user, create a new one
                dyuserinfo = dyUserInfo(account_user_id)
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(data["id"])
                dyuserinfo.source="Discord"
                sql_session.add(dyuserinfo)
                response=f"\nLinked with Explode user: {data['username']}"
                # await bind.send(reply + f"\nLinked with Explode user: {data['username']}")
        else:
            if (dyuserinfo := await sql_session.get(dyUserInfo,     account_user_id)):
                previous_username = dyuserinfo.dynamite_username
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(data["id"])
                sql_session.add(dyuserinfo)
                response=f"已绑定Explode用户：{data['username']}\n旧用户名：{previous_username}"
                # await bind.send(reply + f"已绑定Explode用户：{data['username']}\n旧用户名：{previous_username}")
            else:
            # no existing record for this user, create a new one
                dyuserinfo = dyUserInfo(account_user_id)
                dyuserinfo.set_username(user_name)
                dyuserinfo.set_user_id(data["id"])
                sql_session.add(dyuserinfo)
                response=f"已绑定Explode用户：{data['username']}"
                # await bind.send(reply + f"已绑定Explode用户：{data['username']}")
    return response
                

# fetch recent record
async def fetch_recent(dyuserinfo:dyUserInfo):
    """
    Fetch the recent record of a user
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                    config.api_base_url + config.user_base_api+dyuserinfo.dynamite_user_id+"/last",
                    headers={"Accept": "application/json,text/plain", "Content-Type": "application/json"},
                    timeout=5,
                )
            resp.raise_for_status()
            # get the data field from the response, which should contain user info if the username exists
        latest_record = resp.json().get("data", [])[0]
    except Exception as exc:
        raise exc
    
    logger.debug(f"Received latest record: {latest_record}")
    
    # recent play record
    set_info = latest_record.get("set_info", {})
    chart_info = latest_record.get("chart_info", {})
    r=latest_record.get("r", "UnRanked")
    music_name=set_info.get("music_name")
    difficulty_class=chart_info.get("difficulty_class")
    difficulty_value=chart_info.get("difficulty_value")
    score=latest_record.get("score")
    perfect=latest_record.get("perfect")
    good=latest_record.get("good")
    miss=latest_record.get("miss")
    playtime=latest_record.get("upload_time")
    playtime=datetime.fromisoformat(playtime)

    if dyuserinfo.source=="Discord":
        playtime=playtime.astimezone(pytz.timezone("UTC")).strftime("%Y-%m-%d %H:%M:%S %Z %z")
    else:
        playtime=playtime.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z %z")
    set_id=latest_record.get("set_id")
    accuracy = calculate_acc(perfect, good, miss)
    user_name=dyuserinfo.dynamite_username

    return r,music_name,difficulty_class,difficulty_value,score,perfect,good,miss,playtime,set_id,accuracy,user_name

async def generate_image(**kwargs):
    """
    draw recent record image
    """
    r=kwargs.get("r", "UnRanked")
    music_name=kwargs.get("music_name")
    difficulty_class=kwargs.get("difficulty_class")
    difficulty_value=kwargs.get("difficulty_value")
    score=kwargs.get("score")
    perfect=kwargs.get("perfect")
    good=kwargs.get("good")
    miss=kwargs.get("miss")
    playtime=kwargs.get("playtime")

    set_id=kwargs.get("set_id")
    accuracy = kwargs.get("accuracy")
    user_name=kwargs.get("user_name")

    # in image format

    bg_file = image_asset_dir / "bg.png"
    bg_asset_file = image_asset_dir / "bgfront2.png"
    new_image = Image.open(bg_file).convert("RGB")
    assets = Image.open(bg_asset_file)
    Logo= Image.open(image_asset_dir / "Logo.png").convert("RGBA")
    # Logo = Logo.resize((200,256))

    # rounded rectangle mask for background image
    image_mask = Image.new("L", (1900,830), 0)
    draw_mask = ImageDraw.Draw(image_mask)
    draw_mask.rounded_rectangle((0,0,1900,830),70, fill=255)

    bg_image: Image.Image

    try:
        # There are redirects in the bg download url, so we need to allow redirects in the http client
        async with httpx.AsyncClient(follow_redirects=True) as client:
            bg_response = await client.get(config.bg_download_url_base+str(set_id), timeout=10)
            bg_response.raise_for_status()
            bg_image = Image.open(BytesIO(bg_response.content)).convert("RGBA")
            bg_image = bg_image.resize((1900,830))
    except Exception as e:
        logger.warning(f"Failed to download background image: {e}")
        bg_image = Image.new("RGBA", (1900,830), (50,50,50,255))

    bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=10))

    new_image.paste(bg_image,(50,200),image_mask)
    new_image.paste(Logo,(40,15),Logo)
            
    new_image.paste(assets,(0,0),assets)

    #rank icon
    new_image=paste_rank(new_image,int(score))

    draw=ImageDraw.Draw(new_image)
    #load fonts
    eurostyle=ImageFont.truetype(str(image_asset_dir / "EuroStyle Normal.ttf"), 100)
    eurostyle_bold=ImageFont.truetype(str(image_asset_dir / "EurostileBold.ttf"), 100)
    eurostyle_italic=ImageFont.truetype(str(image_asset_dir / "EurostileOblique.ttf"), 160)
    eurostyle_italic_small=ImageFont.truetype(str(image_asset_dir / "EurostileOblique.ttf"), 50)
    title=ImageFont.truetype(str(image_asset_dir / "SourceHanSansCN-Medium.otf"), 100)
    title_small=ImageFont.truetype(str(image_asset_dir / "SourceHanSansCN-Medium.otf"), 55)
    player_info_font=ImageFont.truetype(str(image_asset_dir / "SourceHanSansCN-Medium.otf"), 70)
    saira_small=ImageFont.truetype(str(image_asset_dir / "Saira-Regular.ttf"), 75)
    saira_time=ImageFont.truetype(str(image_asset_dir / "Saira-Regular.ttf"), 50)
    saira_score=ImageFont.truetype(str(image_asset_dir / "Saira-Regular.ttf"), 140)

    draw.text((270,50), f"Recent Record", font=eurostyle_italic, fill=(255,255,255))
            
    # difficulty icon
    match(difficulty_class-1):
        case 0:
            draw.circle((200,300), 75,fill=(56,142,60))
        case 1:
            draw.circle((200,300),75, fill=(0,145,234))
        case 2:
            draw.circle((200,300), 75, fill=(244,67,54))
        case 3:
            draw.circle((200,300), 75, fill=(106,27,154))
        case 4:
            draw.circle((200,300), 75, fill=(170,170,170))
        case 5:
            draw.circle((200,300), 75, fill=(0,0,0))
    #title text box
    temp_image=Image.new("RGB",(1,1),(0,0,0))
    temp_draw=ImageDraw.Draw(temp_image)
    bbox=temp_draw.textbbox((0,0),f"{music_name}",title,anchor="lt",stroke_width=3)

    # this is the text_width
    text_width=bbox[2]-bbox[0]
            

    #draw text
    draw.text((200,256), f"{difficulty_value}", font=eurostyle_bold, fill=(255,255,255),anchor="ma",align="center")
    # Music name
    if text_width<=1650:
        draw.text((300,290), f"{music_name}", font=title, fill=(0,0,0),anchor="lm",stroke_width=3, stroke_fill=(255,255,255))
    else:
        tlen=len(music_name)
        logger.debug(f"Title length:{tlen}")
        # music_name=music_name[:60]+"\n"+music_name[61:]
        draw.text((300,270), f"{music_name}", font=title_small, fill=(0,0,0),stroke_width=2, stroke_fill=(255,255,255))
    #score
    draw.text((800,400), f"{score}", font=saira_score, fill=(255,255,255),anchor="ma",align="center")
    #player
    draw.text((430,630), f"Player:",align="center", anchor="ma",font=saira_small, fill=(255,255,255))
    draw.text((430,740), f"{user_name}",align="center", anchor="ma",font=player_info_font, fill=(255,255,255))
    #R points
    draw.text((1025,630), f"R.Points:\n{r}",align="center", anchor="ma",font=saira_small, fill=(255,255,255))
    draw.text((700,860), f"Acc: {accuracy*100:.2f}%",align="center", anchor="ma",font=saira_small, fill=(255,255,255))
    # play details
    draw.text((1340,435), f"Perfect", font=saira_small, fill=(255,255,255))
    draw.text((1340,645), f"Good", font=saira_small, fill=(255,255,255))
    draw.text((1340,855), f"Miss", font=saira_small, fill=(255,255,255))
    draw.text((1870,435), f"{perfect}", anchor="ra",font=saira_small, fill=(255,255,255))
    draw.text((1870,645), f"{good}", anchor="ra",font=saira_small, fill=(255,255,255))
    draw.text((1870,855), f"{miss}", anchor="ra",font=saira_small, fill=(255,255,255))
    # play time
    draw.text((30,1050), f"Played at: {playtime}",font=saira_time, fill=(255,255,255))

    return new_image

def generate_temp_filename() -> str:
    """生成唯一的临时文件名"""
    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(1000, 9999)
    return f"processed_{timestamp}_{random_suffix}.png"

async def cleanup_temp_file(file_path: Path, delay: float = 7.0):
    """清理临时文件"""
    await asyncio.sleep(delay)
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass