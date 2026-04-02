# Copied and modified from yuhaoyuhao7370's b20 image generator

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

import base64
import asyncio
from functools import lru_cache

import httpx
from decimal import Decimal
from io import BytesIO
from typing import Any
from pathlib import Path

from nonebot import logger

from nonebot import get_plugin_config
import nonebot_plugin_localstore as store

from .config import Config
from .utils import fetch_b20

config = get_plugin_config(Config)
image_asset_dir = Path(__file__).parent / "assets"
image_asset_dir.mkdir(exist_ok=True)


# ===================Wrapper=====================
def _img_to_b64_sync(img: Image.Image) -> str:
    with BytesIO() as bytes_io:
        img.save(bytes_io, "PNG")
        raw = bytes_io.getvalue()
    return "base64://" + base64.b64encode(raw).decode()


async def img2b64(img: Image.Image) -> str:
    return await asyncio.to_thread(_img_to_b64_sync, img)


async def wrapper_draw_best_20(
    uuid: str, username: str, timeout_seconds: int = 30
) -> str:
    image = await asyncio.wait_for(
        draw_best20(uuid, username),
        timeout=max(5, int(timeout_seconds)),
    )
    return await img2b64(image)


async def wrapper_draw_best_20_binary(
    uuid: str, username: str, timeout_seconds: int = 30
) -> Image.Image:
    image = await asyncio.wait_for(
        draw_best20(uuid, username),
        timeout=max(5, int(timeout_seconds)),
    )
    return image


# ===================B20 Image=====================
TAN75 = 0.266

DIFFICULTY_TEXTS = [
    "UNKNOWN",
    "CASUAL",
    "NORMAL",
    "HARD",
    "MEGA",
    "GIGA",
    "TERA",
]

_COVER_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(10)
_COVER_LOCKS: dict[str, asyncio.Lock] = {}


def _difficulty_text(difficulty_class: int) -> str:
    if 0 <= difficulty_class < len(DIFFICULTY_TEXTS):
        return DIFFICULTY_TEXTS[difficulty_class]
    return DIFFICULTY_TEXTS[0]


def _open_image(image_path: str | Path) -> Image.Image:
    with open(image_path, "rb") as file:
        return Image.open(file).convert("RGBA")


# 画平行四边形
def _get_parallelogram_image(width: int, height: int, color: str) -> Image.Image:
    image = Image.new(mode="RGB", size=(width, height), color=color)
    mask = Image.new("L", image.size, color=255)
    draw = ImageDraw.Draw(mask)
    draw.polygon((0, 0, int(height * TAN75), 0, 0, height), fill=0)
    draw.polygon((width, 0, width - int(height * TAN75), height, width, height), fill=0)
    image.putalpha(mask)
    return image


def _get_illustration_image(
    path: str | Path, width_to: int, height_to: int
) -> Image.Image:
    image = _open_image(path)
    width, height = image.size
    target_w = height * width_to / height_to
    target_h = width * height_to / width_to
    if width / height > width_to / height_to:
        image = image.crop(
            (int((width - target_w) / 2), 0, int((width + target_w) / 2), height)
        )
    else:
        image = image.crop(
            (0, int((height - target_h) / 2), width, int((height + target_h) / 2))
        )
    image = image.resize((width_to, height_to))

    mask = Image.new("L", image.size, color=255)
    draw = ImageDraw.Draw(mask)
    draw.polygon((0, 0, int(height_to * TAN75), 0, 0, height_to), fill=0)
    draw.polygon(
        (width_to, 0, width_to - int(height_to * TAN75), height_to, width_to, height_to),
        fill=0,
    )
    image.putalpha(mask)
    return image


@lru_cache(maxsize=128)
def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font_path: str,
    font_size: int,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    anchor: str = "lt",
) -> None:
    draw.text(
        position, text, fill=color, font=_load_font(font_path, font_size), anchor=anchor
    )


_DIFFICULTY_PARALLELOGRAMS = [
    _get_parallelogram_image(83, 44, "#FFFFFF"),
    _get_parallelogram_image(164, 92, "#51AF44"),
    _get_parallelogram_image(164, 92, "#3173B3"),
    _get_parallelogram_image(164, 92, "#BE2D23"),
    _get_parallelogram_image(164, 92, "#F601FF"),
    _get_parallelogram_image(164, 92, "#6F6F6F"),
    _get_parallelogram_image(164, 92, "#000000"),
]

_BACKGROUND_PARALLELOGRAM = _DIFFICULTY_PARALLELOGRAMS[0]


def _score_tier(score: int) -> int:
    if score == 1000000:
        return 0
    if 980000 <= score < 1000000:
        return 1
    if 950000 <= score < 980000:
        return 2
    if 900000 <= score < 950000:
        return 3
    if 800000 <= score < 900000:
        return 4
    if 700000 <= score < 800000:
        return 5
    if 600000 <= score < 700000:
        return 6
    if 500000 <= score < 600000:
        return 7
    if 400000 <= score < 500000:
        return 8
    return 9


@lru_cache(maxsize=32)
def _load_rank_image(resource_path: str, tier: int) -> Image.Image:
    return _open_image(Path(resource_path) / f"UI1_Difficulties_{tier}.png")
    # return _open_image(Path(resource_path) / f"ranks/UI1_Difficulties_{tier}.png")


def _get_rank_image(resource_path: str, score: int) -> Image.Image:
    return _load_rank_image(resource_path, _score_tier(score)).copy()


def _get_cover_lock(set_id: str) -> asyncio.Lock:
    lock = _COVER_LOCKS.get(set_id)
    if lock is None:
        lock = asyncio.Lock()
        _COVER_LOCKS[set_id] = lock
    return lock


async def _download_cover_if_needed(
    set_id: str,
    cover_path: Path,
    cover_service_url: str,
    timeout_seconds: int,
) -> None:
    if cover_path.exists():
        return
    if not cover_service_url:
        return

    lock = _get_cover_lock(set_id)
    async with lock:
        if cover_path.exists():
            return

        url = cover_service_url.rstrip("/") + "/" + set_id
        # url = f"{cover_service_url.rstrip('/')}/d/explode/bg/{set_id}"
        try:
            async with _COVER_DOWNLOAD_SEMAPHORE:
                logger.opt(colors=True).info(
                    f"Downloading cover for: <yellow>{set_id}</yellow> from url: <blue>{url}</blue>"
                )
                async with httpx.AsyncClient(
                    timeout=timeout_seconds, follow_redirects=True
                ) as client:
                    response = await client.get(url)
                    if response.status_code != 200:
                        logger.debug(
                            f"Download cover response error. Response status: {response.status_code}"
                        )
                        return
                    data = response.content
                    if not data:
                        logger.debug("No data acquired.")
                        return
                    cover_path.parent.mkdir(parents=True, exist_ok=True)
                    cover_path.write_bytes(data)
        except Exception as exc:
            logger.opt(colors=True).warning(
                f"Dynamite cover download failed for <yellow>{set_id}</yellow>: {exc}"
            )
        finally:
            if not lock.locked():
                _COVER_LOCKS.pop(set_id, None)


def _safe_accuracy(perfect: int, good: int, miss: int) -> str:
    total = perfect + good + miss
    if total <= 0:
        return "0.00"
    value = Decimal((perfect + good * 0.5) / total * 100.0).quantize(
        Decimal("0.01"), rounding="ROUND_HALF_UP"
    )
    return str(value)


def _safe_r_value(raw: Any) -> int:
    try:
        return int(Decimal(raw or 0).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
    except Exception:
        return 0


def _render_best20_image(
    username: str,
    records: list[dict[str, Any]],
    *,
    resource_path: str,
    font_path: str,
) -> Image.Image:
    background_path = Path(resource_path) / "BackGround.png"
    default_cover_path = Path(resource_path) / "default.png"

    image = _open_image(background_path)
    draw = ImageDraw.Draw(image)
    x0, y0 = 196, 682

    total_r = 0
    count = 1
    for record in records:
        score = int(record.get("score", 0))
        perfect = int(record.get("perfect", 0))
        good = int(record.get("good", 0))
        miss = int(record.get("miss", 0))
        chart_info = record.get("chart_info", {}) or {}
        set_info = record.get("set_info", {}) or {}

        difficulty_class = int(chart_info.get("difficulty_class", 0))
        if not 0 <= difficulty_class < len(_DIFFICULTY_PARALLELOGRAMS):
            difficulty_class = 0
        difficulty_value = chart_info.get("difficulty_value", 0)
        difficulty_text = _difficulty_text(difficulty_class)

        set_id = str(set_info.get("id", ""))
        music_name = str(set_info.get("music_name", "Unknown"))
        r_value = _safe_r_value(record.get("r"))
        total_r += r_value

        if count % 2 == 0:
            x = x0 + 1097
            y = y0 + (count // 2 - 1) * 317 + 105
        else:
            x = x0
            y = y0 + (count // 2) * 317

        cover_path = store.get_plugin_data_dir() / "cover" / f"{set_id}.webp"

        try:
            illustration_image = _get_illustration_image(cover_path, 408, 230)
        except Exception:
            illustration_image = _get_illustration_image(default_cover_path, 408, 230)

        image.alpha_composite(_BACKGROUND_PARALLELOGRAM, (x - 21, y))
        _draw_text(
            draw,
            (x + 20, y + 22),
            f"#{count}",
            font_path,
            30,
            (0, 0, 0, 255),
            anchor="mm",
        )
        image.alpha_composite(illustration_image, (x, y))
        image.alpha_composite(
            _DIFFICULTY_PARALLELOGRAMS[difficulty_class], (x - 72, y + 138)
        )
        _draw_text(
            draw,
            (x + 16, y + 163),
            f"{difficulty_text} {difficulty_value}",
            font_path,
            26,
            anchor="mm",
        )
        _draw_text(draw, (x + 9, y + 198), f"R: {r_value}", font_path, 38, anchor="mm")
        _draw_text(draw, (x + 655, y + 44), music_name, font_path, 32, anchor="mm")
        _draw_text(
            draw, (x + 530, y + 131), f"{score}".zfill(7), font_path, 37, anchor="ls"
        )
        _draw_text(
            draw,
            (x + 738, y + 131),
            f"{_safe_accuracy(perfect, good, miss)}%",
            font_path,
            27,
            anchor="ls",
        )

        rank_image = _get_rank_image(resource_path, score).resize((115, 115))
        image.alpha_composite(rank_image, (x + 392, y + 80))

        _draw_text(
            draw,
            (x + 525, y + 190),
            "Perfect",
            font_path,
            22,
            (255, 183, 0, 255),
            anchor="ls",
        )
        _draw_text(draw, (x + 630, y + 181), str(perfect), font_path, 22, anchor="mm")
        _draw_text(
            draw,
            (x + 663, y + 190),
            "Good",
            font_path,
            22,
            (76, 171, 255, 255),
            anchor="ls",
        )
        _draw_text(draw, (x + 740, y + 181), str(good), font_path, 22, anchor="mm")
        _draw_text(
            draw,
            (x + 765, y + 190),
            "Miss",
            font_path,
            22,
            (255, 76, 76, 255),
            anchor="ls",
        )
        _draw_text(draw, (x + 837, y + 181), str(miss), font_path, 22, anchor="mm")

        count += 1

    _draw_text(draw, (1430, 330), username, font_path, 68, anchor="ls")
    _draw_text(draw, (1430, 430), str(total_r), font_path, 68, anchor="ls")
    return image


async def draw_best20(uuid: str, dyuser: str) -> Image.Image:

    resource_path = image_asset_dir
    font_path = image_asset_dir / "sy.ttf"

    # cover_service_url = config.bg_download_openlist
    cover_service_url = config.bg_download_url_base
    timeout_seconds = max(3, config.http_timeout_seconds)
    # logger.debug(f"Received dynamite bind user info: {dyuser}")
    username = dyuser
    records = await fetch_b20(uuid)

    if not resource_path or not font_path:
        raise RuntimeError("resource_path/font_path is not configured")

    cover_tasks = []
    for record in records:
        set_info = record.get("set_info", {}) or {}
        set_id = str(set_info.get("id", "")).strip()
        if not set_id:
            continue
        cover_path = store.get_plugin_data_dir() / "cover" / f"{set_id}.webp"

        if cover_path.exists():
            continue
        cover_tasks.append(
            _download_cover_if_needed(
                set_id=set_id,
                cover_path=cover_path,
                cover_service_url=cover_service_url,
                timeout_seconds=timeout_seconds,
            )
        )

    if cover_tasks:
        await asyncio.gather(*cover_tasks, return_exceptions=True)

    return await asyncio.to_thread(
        _render_best20_image,
        username,
        records,
        resource_path=resource_path,
        font_path=font_path,
    )
