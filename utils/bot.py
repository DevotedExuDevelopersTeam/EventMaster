import importlib
import inspect
import os
import sys

import disnake
from disnake.ext import commands

from utils.constants import SERVER_ID
from utils.database import Database
from utils.logs import Logger

REQUIRED_DIRS = ["data", "data/trophies", "data/logs"]
for d in REQUIRED_DIRS:
    if not os.path.exists(d):
        os.mkdir(d)


class Bot(commands.InteractionBot):
    def __init__(self):
        intents = disnake.Intents(
            emojis=True,
            guild_messages=True,
            guild_scheduled_events=True,
            guild_typing=True,
            guilds=True,
            members=True,
            message_content=True,
            presences=True,
        )
        self.db = Database()
        self.log = Logger()
        self.server: disnake.Guild | None = None

        super().__init__(
            intents=intents,
            activity=disnake.Activity(
                name="for event ideas", type=disnake.ActivityType.watching
            ),
        )

    async def start(self, *args, **kwargs):
        self.log.info("Starting bot...")
        await self.db.connect()

        await super().start(*args, **kwargs)

    def run(self):
        self.log.info("Loading extensions...")
        self.load_all_extensions("ext")
        try:
            super().run(os.environ["TOKEN"])
        except KeyError:
            self.log.critical("Required env variable TOKEN is unset")
            sys.exit(1)

    async def on_ready(self):
        self.log.ok("Bot is ready")
        self.server = self.get_guild(SERVER_ID)

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        self.log.error(
            "Exception occurred at %s", event_method, exc_info=sys.exc_info()
        )

    async def close(self) -> None:
        self.log.info("Shutting down...")
        await self.db.close()
        self.log.ok("Bot was shut down successfully")

    def auto_setup(self, module_name: str):
        module = importlib.import_module(module_name, None)
        sys.modules[module_name] = module
        members = inspect.getmembers(
            module,
            lambda x: inspect.isclass(x)
            and issubclass(x, commands.Cog)
            and x.__name__ != "Cog",
        )
        for member in members:
            self.add_cog(member[1](self))

        self.log.ok("%s loaded", module_name)

    def load_all_extensions(self, path: str):
        for file in os.listdir(path):
            full_path = os.path.join(path, file).replace("\\", "/")
            if os.path.isdir(full_path):
                self.load_all_extensions(full_path)

            elif full_path.endswith(".py"):
                self.auto_setup(full_path[:-3].replace("/", "."))


class Cog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
