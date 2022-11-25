import disnake
import pendulum

from utils.logs import Logger


class Session:
    def __init__(self, channel: disnake.TextChannel):
        self.total_messages: int = 0
        self.started_at = pendulum.now()
        self.users: dict[
            int, int
        ] = (
            {}
        )  # a dict where keys are user IDs and values are amounts of their messages
        self.stats: list[int] = []  # list with amount of messages for each minute
        self.id = f"{channel.name}-{int(self.started_at.timestamp())}"
        self.log = Logger("session-" + self.id)
        self.log.info(f"Initiated track session for channel {channel.id}")

    @property
    def total_participants(self) -> int:
        return len(self.users)

    def register_message(self, msg: disnake.Message):
        current_minute: int = (pendulum.now() - self.started_at).seconds // 60
        registered_minutes = len(self.stats) - 1
        if registered_minutes == current_minute:
            self.stats[current_minute] += 1
        else:
            self.stats += [0] * (current_minute - len(self.stats) + 1)
            self.stats.append(1)

        self.users[msg.author.id] = self.users.get(msg.author.id, 0) + 1
        self.total_messages += 1

    def get_top_users(self, limit) -> list[int]:
        # noinspection PyTypeChecker
        users: list[tuple[int, int]] = list(self.users.items())
        users.sort(
            key=lambda e: e[1], reverse=True
        )  # TODO probably wanna do optimization
        return [i[0] for i in users[:limit]]
