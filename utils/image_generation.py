import asyncio
import os
from io import BytesIO
from pathlib import Path
from typing import Sequence
from urllib.request import build_opener, install_opener, urlopen

import disnake
from PIL import Image, ImageDraw, ImageFont, ImageOps

from utils.database import EventUser
from utils.deco import fnum

opener = build_opener()
opener.addheaders = [("Authorization", f"Bot {os.environ['TOKEN']}")]
install_opener(opener)


with Image.open("res/templates/profile.png") as img:
    PROF_BASE_IMAGE = img.copy()

PROF_NAME_FONT = ImageFont.truetype("res/fonts/Neucha.ttf", 122)
PROF_NAME_COLOR = "#38FFF5"
PROF_NAME_POS = (120, 179)

PROF_LB_FONT = ImageFont.truetype("res/fonts/LuckiestGuy.ttf", 181)
PROF_LB_COLOR = "#42F2F4"
PROF_LB_POS = (1892, 172)

PROF_PFP_POS = (333, 589)
PROF_PFP_SIZE = (316, 316)

PROF_STATS_FONT = ImageFont.truetype("res/fonts/Neucha.ttf", 94)
PROF_STATS_COLOR = "#F7F73E"
PROF_STATS_POS_X = 1814
PROF_STATS_POS_Y_START = 343
PROF_STATS_POS_Y_STEP = 137
PROF_STATS_POS_Y_STOP = PROF_STATS_POS_Y_START + PROF_STATS_POS_Y_STEP * 2 + 1

PROF_TR_EMPTY_COLOR = "#EBEBEB"
PROF_TR_EMPTY_SIZE = (48, 48)
PROF_TR_TROPHY_SIZE = (130, 130)
PROF_TR_POS_Y = 835
PROF_TR_POS_X_START = 694
PROF_TR_POS_X_STEP = 180
PROF_TR_POS_X_STOP = PROF_TR_POS_X_START + PROF_TR_POS_X_STEP * 6 + 1


with Image.open("res/templates/stats.png") as img:
    STATS_BASE_IMAGE = img.copy()

STATS_NAME_FONT = ImageFont.truetype("res/fonts/LuckiestGuy.ttf", 142)
STATS_NAME_COLOR = "#38FFF5"
STATS_NAME_POS = (125, 194)

STATS_TOP_FONT = ImageFont.truetype("res/fonts/CarterOne.ttf", 61)
STATS_TOP_COLOR = "#4BFFAE"
STATS_TOP_POS_X = 45
STATS_TOP_POS_Y_START = 480
STATS_TOP_POS_Y_STEP = 104
STATS_TOP_POS_Y_STOP = STATS_TOP_POS_Y_START + STATS_TOP_POS_Y_STEP * 4 + 1

STATS_STATS_FONT = ImageFont.truetype("res/fonts/Neucha.ttf", 94)
STATS_STATS_COLOR = "#F7F73E"
STATS_STATS_POS_X = 1945
STATS_STATS_POS_Y_START = 465
STATS_STATS_POS_Y_STEP = 167
STATS_STATS_POS_Y_STOP = STATS_STATS_POS_Y_START + STATS_STATS_POS_Y_STEP * 2 + 1


def circle_img(im: Image.Image) -> Image.Image:
    mask = Image.new("L", im.size)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + im.size, fill="#fff")

    out = ImageOps.fit(im, im.size, centering=(0.5, 0.5))
    out.putalpha(mask)

    return out


def get_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill="#fff")
    return mask


def center_to_box(
    center: tuple[int, int], size: tuple[int, int]
) -> tuple[int, int, int, int]:
    s0 = size[0] // 2
    s1 = size[1] // 2
    c0 = center[0]
    c1 = center[1]
    return c0 - s0, c1 - s1, c0 + s0, c1 + s1


async def draw_statistics_card(
    channel_name: str,
    track_time: str,
    messages_sent: int,
    total_participants: int,
    top_users: Sequence[str],
) -> BytesIO:
    return await asyncio.get_event_loop().run_in_executor(
        None,
        __draw_statistics_card,
        channel_name,
        track_time,
        messages_sent,
        total_participants,
        top_users,
    )


def __draw_statistics_card(
    channel_name: str,
    track_time: str,
    messages_sent: int,
    total_participants: int,
    top_users: Sequence[str],
) -> BytesIO:
    if len(top_users) > 5:
        top_users = top_users[:5]
    image = STATS_BASE_IMAGE.copy()
    draw = ImageDraw.Draw(image)

    draw.text(
        xy=STATS_NAME_POS,
        text="#" + channel_name,
        fill=STATS_NAME_COLOR,
        font=STATS_NAME_FONT,
        anchor="lm",
        align="left",
    )

    for i, pos_y, user in zip(
        range(1, len(top_users) + 1),
        range(STATS_TOP_POS_Y_START, STATS_TOP_POS_Y_STOP, STATS_TOP_POS_Y_STEP),
        top_users,
    ):
        draw.text(
            xy=(STATS_TOP_POS_X, pos_y),
            text=f"#{i}. {user}",
            fill=STATS_TOP_COLOR,
            font=STATS_TOP_FONT,
            anchor="lm",
            align="left",
        )

    for pos_y, stat in zip(
        range(STATS_STATS_POS_Y_START, STATS_STATS_POS_Y_STOP, STATS_STATS_POS_Y_STEP),
        (track_time, fnum(messages_sent), str(total_participants)),
    ):
        draw.text(
            xy=(STATS_STATS_POS_X, pos_y),
            text=stat,
            fill=STATS_STATS_COLOR,
            font=STATS_STATS_FONT,
            anchor="ra",
            align="right",
        )

    io = BytesIO()
    image.save(io, format="png")
    io.seek(0)
    return io


async def draw_profile_card(
    user: disnake.Member,
    event_user: EventUser,
) -> BytesIO:
    return await asyncio.get_event_loop().run_in_executor(
        None, __draw_profile_card, user, await event_user.get_lb_pos(), event_user
    )


def __draw_profile_card(
    user: disnake.Member, lb_pos: int, event_user: EventUser
) -> BytesIO:
    image = PROF_BASE_IMAGE.copy()
    draw = ImageDraw.Draw(image)

    draw.text(
        xy=PROF_NAME_POS,
        text=str(user),
        fill=PROF_NAME_COLOR,
        font=PROF_NAME_FONT,
        anchor="lm",
        align="left",
    )

    draw.text(
        xy=PROF_LB_POS,
        text=f"#{lb_pos}",
        fill=PROF_LB_COLOR,
        font=PROF_LB_FONT,
        anchor="rm",
        align="right",
    )

    with Image.open(urlopen(user.display_avatar.url)) as pfp:
        pfp = pfp.resize(PROF_PFP_SIZE)
        image.paste(
            pfp, center_to_box(PROF_PFP_POS, PROF_PFP_SIZE), get_mask(PROF_PFP_SIZE)
        )

    for pos_y, stat in zip(
        range(PROF_STATS_POS_Y_START, PROF_STATS_POS_Y_STOP, PROF_STATS_POS_Y_STEP),
        [fnum(event_user.points), event_user.total_events, event_user.won_events],
    ):
        draw.text(
            xy=(PROF_STATS_POS_X, pos_y),
            text=str(stat),
            fill=PROF_STATS_COLOR,
            font=PROF_STATS_FONT,
            anchor="ra",
            align="right",
        )

    for i, pos_x in enumerate(
        range(PROF_TR_POS_X_START, PROF_TR_POS_X_STOP, PROF_TR_POS_X_STEP)
    ):
        if len(event_user.trophy_ids) <= i:
            draw.ellipse(
                center_to_box((pos_x, PROF_TR_POS_Y), PROF_TR_EMPTY_SIZE),
                fill=PROF_TR_EMPTY_COLOR,
            )
        else:
            with Image.open(
                Path("data/trophies/", event_user.trophy_ids[i] + ".png")
            ) as tr:
                resized_tr = tr.resize(PROF_TR_TROPHY_SIZE)
                image.paste(
                    resized_tr,
                    center_to_box((pos_x, PROF_TR_POS_Y), PROF_TR_TROPHY_SIZE),
                    resized_tr.convert("RGBA"),
                )

    io = BytesIO()
    image.save(io, format="png")
    io.seek(0)
    return io
