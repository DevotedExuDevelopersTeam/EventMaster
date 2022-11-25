from io import BytesIO

import disnake
import pendulum
from disnake.ext import commands

from utils.bot import Bot, Cog
from utils.image_generation import draw_statistics_card
from utils.tracking import Session


class Tracking(Cog):
    def __init__(self, bot: Bot):
        super().__init__(bot)
        self.sessions: dict[int, Session] = {}

    def new_session(self, channel: disnake.TextChannel):
        self.sessions[channel.id] = Session(channel)

    async def end_session(self, channel: disnake.TextChannel) -> BytesIO:
        session = self.sessions.pop(channel.id)
        session.log.info("Activity tracking finished")
        delta = pendulum.now() - session.started_at
        return await draw_statistics_card(
            channel.name,
            f"{delta.hours}:{delta.minutes}:{delta.seconds}",
            session.total_messages,
            session.total_participants,
            list(
                map(
                    lambda e: str(channel.guild.get_member(e)), session.get_top_users(5)
                )
            ),
        )

    @Cog.listener()
    async def on_message(self, msg: disnake.Message):
        if msg.author.bot or msg.channel.id not in self.sessions:
            return

        self.sessions[msg.channel.id].register_message(msg)

    @commands.slash_command(
        name="starttrack", description="Starts activity tracking in selected channel"
    )
    async def starttrack(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = None,
    ):
        channel = channel or inter.channel
        self.new_session(channel)
        await inter.send(f"Started activity tracking in {channel.mention}")

    @commands.slash_command(
        name="stoptrack", description="Stops activity tracking in selected channel"
    )
    async def stoptrack(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = None,
    ):
        channel = channel or inter.channel
        if channel.id not in self.sessions:
            await inter.send(
                f"There's no activity tracking session in {channel.mention}"
            )
            return
        await inter.response.defer()
        pic = await self.end_session(channel)
        await inter.send(file=disnake.File(pic, "stats.png"))
