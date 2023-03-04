from utils.constants import ENUMERATION_EMOJIS


def fnum(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def emoji_enum(options: list[str]) -> str:
    txt = ""
    for e, option in zip(ENUMERATION_EMOJIS, options):
        txt += f"{e} {option}\n"
    return txt.strip("\n")
