from typing import cast

import asyncpg
import disnake
from disnake.ext import commands, tasks

from utils.bot import Cog
from utils.constants import ENUMERATION_EMOJIS, POLLS_ROLE_ID
from utils.deco import emoji_enum
from utils.views import ConfirmationView, Modal


class Polls(Cog):
    def __init__(self, *args):
        super().__init__(*args)
        self._requested_updates: dict[int, set[int]] = {}
        self._messages: dict[int, disnake.Message] = {}
        self.update_polls.start()

    @tasks.loop(seconds=5)
    async def update_polls(self):
        for message_id in self._requested_updates:
            required_options = self._requested_updates[message_id]
            message = self._messages[message_id]
            view = disnake.ui.View.from_message(message)
            for item in view.children:
                if not (isinstance(item, disnake.ui.Button) and item.custom_id.startswith("option-")):
                    continue
                if (option := int(item.custom_id.split("-")[1])) in required_options:
                    votes: int = await self.bot.db.fetchval(
                        "SELECT COUNT(*) FROM polls WHERE message_id = $1 AND option_id = $2",
                        message_id,
                        option,
                    )
                    item.label = f"{votes} vote{'' if votes == 1 else 's'}"
            await message.edit(view=view)
            view.stop()

    @Cog.listener(disnake.Event.raw_message_delete)
    async def polls_cleanup(self, payload: disnake.RawMessageDeleteEvent):
        await self.bot.db.execute("DELETE FROM polls WHERE message_id = $1", payload.message_id)

    @Cog.listener(disnake.Event.button_click)
    async def polls_listener(self, inter: disnake.MessageInteraction):
        button = cast(disnake.Button, inter.component)
        if not button.custom_id.startswith("option-"):
            return
        option_id = int(button.custom_id.split("-")[1])
        message_id = inter.message.id
        user_id = inter.author.id

        self._messages[message_id] = inter.message

        try:
            await self.bot.db.execute(
                "INSERT INTO polls (message_id, option_id, member_id) VALUES ($1, $2, $3)",
                message_id,
                option_id,
                user_id,
            )
            await inter.send("Registered your vote!", ephemeral=True)
        except asyncpg.UniqueViolationError:
            old_option: int = await self.bot.db.fetchval(
                "SELECT option_id FROM polls WHERE member_id = $1 AND message_id = $2",
                user_id,
                message_id,
            )
            if old_option == option_id:
                await inter.send("You already voted for this option!", ephemeral=True)
                return
            await self.bot.db.execute(
                "UPDATE polls SET option_id = $1 WHERE member_id = $2 AND message_id = $3",
                option_id,
                user_id,
                message_id,
            )
            await inter.send("Overwrote your vote!", ephemeral=True)
            self._request_update(message_id, old_option)

        self._request_update(message_id, option_id)

    def _request_update(self, message_id: int, option_id: int):
        if message_id not in self._requested_updates:
            self._requested_updates[message_id] = set()
        self._requested_updates[message_id].add(option_id)

    @commands.slash_command(name="poll")
    async def poll(
        self,
        inter: disnake.ApplicationCommandInteraction,
        topic: str,
        channel: disnake.TextChannel | None = None,
        poll_color: disnake.Color | None = None,
    ):
        """
        Create a new poll with set topic
        """
        channel = channel or inter.channel
        color = poll_color or disnake.Color.random()
        modal = Modal(
            title="Specify options",
            components=[
                disnake.ui.TextInput(
                    label="Options",
                    custom_id="options",
                    style=disnake.TextInputStyle.paragraph,
                    placeholder="""Input poll options, each option on new line.""",
                )
            ],
        )
        await inter.response.send_modal(modal)
        m_inter = await modal.wait()
        options: list[str] = list(
            map(
                lambda x: x.strip().capitalize(),
                m_inter.text_values["options"].split("\n"),
            )
        )
        if not 2 <= len(options) <= 10:
            await m_inter.send("There must be at least 2 options, but no more than 10", ephemeral=True)
            return
        view = ConfirmationView(m_inter)
        embed = disnake.Embed(title=topic, description=emoji_enum(options), color=color)
        await m_inter.send("Please check poll preview", embed=embed, view=view)
        inter, res = await view.get_result()
        if not res:
            await inter.send("Operation cancelled")
            return
        await inter.message.edit(view=view)
        await inter.response.defer()

        view = disnake.ui.View()
        for i, (e, _) in enumerate(zip(ENUMERATION_EMOJIS, options), 1):
            view.add_item(
                disnake.ui.Button(
                    style=disnake.ButtonStyle.blurple,
                    label="0 votes",
                    emoji=e,
                    custom_id=f"option-{i}",
                )
            )
        await channel.send(
            f"<@&{POLLS_ROLE_ID}> new poll!",
            embed=embed,
            view=view,
            allowed_mentions=disnake.AllowedMentions.all(),
        )
        view.stop()
        await inter.send("Successfully sent the new poll!")
