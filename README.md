<div align="center">

# DyQuery

_✨ A nonebot2 plugin for getting the latest play record and Best20 score for Dynamite Explode, working well on Onebot V11 and Discord. ✨_

<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

</div>

## 介绍

一个查Dynamite Explode最近游玩记录和best20的插件

## 使用

| 命令 | 说明 |
|----------|----------|
| /dybind <用户名>   | 绑定Dynamite账号 |
| /recent   | 查询最近一次游玩成绩   |
| /recent text  | 查询最近一次游玩成绩(以文字方式输出)  |
| /b20  | 查询自己的Best20成绩  |
| /b20 <用户名> | 查询指定用户的Best20成绩  |

## 安装方法

非正式发布插件注意



将该插件项目中的/src/中的dyquery文件夹复制到机器人的本地插件目录即可完成插件添加。



需要适配器：

nonebot_adapter_onebot

nonebot_adapter_discord



本插件需要以下插件才可以使用:

nonebot_plugin_localstore

nonebot_plugin_orm



其余依赖项:

httpx

pytz

pillow

aiohttp

添加插件并安装后，需要更新数据库：

1. run `nb orm revision -m "Comment for new table for new plugin" --branch-label <labelname>` to create a migration script
2. run `nb orm upgrade` to upgrade the database
3. run `nb orm check` to check if the database matches the bot configuration
   
   
插件配置项:

启用插件:

`DYQUERY_PLUGIN_ENABLED=True`

配置QQ群白名单:
`DYQUERY_WHITE_LIST=[] # 内写QQ群号`

配置QQ群Best20专用白名单(注: 只有同时存在于普通白名单和Best20专用白名单的群才能使用该功能):
`DYQUERY_B20_WHITE_LIST=[] # 内写QQ群号`

配置API URL (ExplodeX架构):

```
API_BASE_URL="http://<服务器地址:api端口>/bomb/v2/"
USER_SEARCH_API="user/search"
USER_BASE_API="user/"
BG_DOWNLOAD_URL_BASE="http://<服务器地址:api端口>/download/cover/480x270_jpg/
BG_DOWNLOAD_OPENLIST="http://<服务器地址:Openlist端口>/"
"
```


