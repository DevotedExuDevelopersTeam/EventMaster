import os
import sys
import uuid
from typing import Any, Self

import asyncpg
from disnake import Message

from utils.logs import Logger


class Database:
    VERSION = 1

    def __init__(self):
        self._pool: asyncpg.Pool | None = None
        self._log: Logger = Logger("DB")

    async def connect(self):
        self._log.info("Connecting to database...")
        try:
            self._pool = await asyncpg.create_pool(
                database=os.environ["DATABASE"],
                user=os.environ["USER"],
                password=os.getenv("PASSWORD", None),
                host="127.0.0.1",
            )
            self._log.ok("Connected successfully")
        except KeyError as e:
            self._log.critical("Required env variable %s is unset", e.args[0])
            sys.exit(1)

        await self.__setup()
        await self.__check_version()

    async def close(self):
        self._log.info("Closing database connection...")
        await self._pool.close()
        self._log.ok("Connection was closed successfully")

    async def __setup(self):
        self._log.info("Executing setup scripts...")
        with open("sql_config.sql") as f:
            await self.execute(f.read())
        self._log.ok("Setup was completed successfully")

    async def __check_version(self):
        self._log.info("Checking database version...")
        version: int = await self.fetchval(
            "SELECT version FROM version_data WHERE id = 0"
        )
        if self.VERSION > version:
            self._log.warning(
                "Database is version %d, but bot uses %d, applying migrations..."
            )
            # TODO migration system
            self._log.error(
                "Migration system is not implemented yet, update is not possible"
            )
            return
        self._log.ok("Database is at latest version")

    async def execute(self, sql, *args):
        await self._pool.execute(sql, *args)

    async def executemany(self, sql, args):
        await self._pool.executemany(sql, args)

    async def fetchall(self, sql, *args) -> list[asyncpg.Record]:
        return await self._pool.fetch(sql, *args)

    async def fetchrow(self, sql, *args) -> asyncpg.Record | None:
        return await self._pool.fetchrow(sql, *args)

    async def fetchval(self, sql, *args) -> Any | None:
        return await self._pool.fetchval(sql, *args)

    def get_event_user(self, id: int) -> "EventUser":
        return EventUser(self, id)

    async def create_event(
        self, id: uuid.UUID, name: str, r_message: Message
    ) -> uuid.UUID:
        await self.execute(
            "INSERT INTO events (id, name, registration_channel_id, registration_message_id) "
            "VALUES ($1, $2, $3, $4)",
            id,
            name,
            r_message.channel.id,
            r_message.id,
        )
        return id

    async def create_group(self, event_id: uuid.UUID, role_id: int, start_time: int):
        await self.execute(
            "INSERT INTO groups (event_id, start_time, role_id) VALUES ($1, $2, $3)",
            event_id,
            start_time,
            role_id,
        )

    async def create_groups(self, groups: list[tuple[int, int, int]]):
        """:param groups: (event_id, role_id, start_time)"""
        await self._pool.executemany(
            "INSERT INTO groups (event_id, role_id, start_time) VALUES ($1, $2, $3)",
            groups,
        )

    async def create_trophy(self, id: str, name: str):
        await self.execute("INSERT INTO trophies (id, name) VALUES ($1, $2)", id, name)

    async def remove_trophy(self, id: str):
        await self.execute("DELETE FROM trophies WHERE id = $1", id)

    async def give_trophy(self, user_id: int, trophy_id: str):
        await self.get_event_user(user_id).ensure_existence()
        await self.execute(
            "INSERT INTO inventories (id, trophy_id) VALUES ($1, $2)",
            user_id,
            trophy_id,
        )

    async def take_trophy(self, user_id: int, trophy_id: str):
        await self.execute(
            "DELETE FROM inventories WHERE id = $1 AND trophy_id = $2",
            user_id,
            trophy_id,
        )


class DataModel:
    key_field = None
    table = None

    def __init__(self, db: Database, key_value: Any):
        self._db = db
        self._key_value = key_value
        setattr(self, self.key_field, key_value)

    async def load(self, ensure_existence: bool = True) -> Self:
        if ensure_existence:
            await self.ensure_existence()

        data = await self._db.fetchrow(
            f"SELECT {', '.join(self.__annotations__.keys())} FROM {self.table} WHERE {self.key_field} = $1",
            self._key_value,
        )
        for k, v in data.items():
            setattr(self, k, v)

        return self

    async def ensure_existence(self):
        await self._db.execute(
            f"INSERT INTO {self.table} ({self.key_field}) VALUES ({self._key_value}) ON CONFLICT DO NOTHING"
        )


class EventUser(DataModel):
    key_field = "id"
    table = "users"

    id: int
    points: int
    total_events: int
    won_events: int

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trophy_ids: list[str] = []

    async def load(self, ensure_existence: bool = True) -> Self:
        await super().load(ensure_existence)
        data = await self._db.fetchall(
            "SELECT trophy_id FROM inventories WHERE id = $1 ORDER BY obtained_on DESC LIMIT 7",
            self.id,
        )
        self.trophy_ids = [row["trophy_id"] for row in data]
        return self

    async def get_lb_pos(self) -> int:
        return await self._db.fetchval(
            "SELECT COUNT(*) FROM users WHERE points >= $1", self.points
        )

    async def update_event_points(self, delta: int):
        await self.ensure_existence()
        await self._db.execute(
            "UPDATE users SET points = points + $2 WHERE id = $1", self.id, delta
        )
