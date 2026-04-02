# now uses sqlite3 for storage
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from nonebot import require

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")

from nonebot_plugin_orm import Model
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import CreateTable

import pickle

import nonebot_plugin_localstore as store

# 获取插件缓存目录
cache_dir = store.get_plugin_cache_dir()
# 获取插件缓存文件
cache_file = store.get_plugin_cache_file("cache.json")
# 获取插件数据目录
data_dir = store.get_plugin_data_dir()

# 获取插件配置目录
config_dir = store.get_plugin_config_dir()
# 获取插件配置文件
config_file = store.get_plugin_config_file("config.json")

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="DyQuery",
    description="A nonebot2 plugin for getting the latest play record for Dynamite Explode, working well on Onebot V11 and Discord.",
    usage="",
    config=Config,
    type="application",
    supported_adapters={"~onebot.v11", "~discord"},  # 适配器支持集合
)

config = get_plugin_config(Config)

# create table if not exists (unnecessary, auto managed by nonebot_plugin_orm)
# CreateTable(dyUserInfo.__table__)

from .handlers import (
    bind,
    query_recent,
    bind_discord,
    query_recent_discord,
    query_recent_discord_text,
)
from .b20_handler import best20, best20_discord

bind_process = bind
query_recent_process = query_recent
b20 = best20
# discord handlers
b_d = bind_discord
q_d = query_recent_discord
q_dt = query_recent_discord_text
b20_d = best20_discord
