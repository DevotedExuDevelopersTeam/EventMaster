import asyncio
import re
from typing import Callable, TYPE_CHECKING, cast

import disnake

if TYPE_CHECKING:
    from utils.bot import Bot

ID_PATTERN = re.compile(r"\d{18,19}")


class EventEndView(disnake.ui.View):
    def __init__(self, user_id: int, participants: list[int]):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.winners: list[int] = []
        self.participants = participants

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if interaction.author.id != self.user_id:
            await interaction.send("This button is not for you", ephemeral=True)
            return False
        return True

    @disnake.ui.button(label="Set Winners", style=disnake.ButtonStyle.blurple)
    async def set_winners(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        button.disabled = True
        await inter.message.edit(view=self)
        await inter.send(
            "Please ping or list IDs of the winners. Example: ```\n123456789012345678 @gamer#1984 @gamer#2020\n```"
        )
        try:
            msg: disnake.Message = await inter.bot.wait_for(
                "message",
                check=lambda m: m.author.id == self.user_id
                and re.findall(ID_PATTERN, m.content),
                timeout=600,
            )
        except asyncio.TimeoutError:
            await inter.send("Response timed out", ephemeral=True)
            await inter.message.delete()
            return

        await msg.delete()
        ids = re.findall(ID_PATTERN, msg.content)
        self.winners = list(map(int, ids))
        for child in self.children:
            if isinstance(child, disnake.ui.Button) and child.custom_id.endswith(
                "winners"
            ):
                child.disabled = False
        await inter.message.edit(view=self)
        await inter.send("Successfully set the winners!")

    @disnake.ui.button(
        label="Add EP to Participants", style=disnake.ButtonStyle.green, row=1
    )
    async def ep_part(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        async def modal_callback(interaction: disnake.ModalInteraction):
            data = interaction.text_values
            try:
                points = abs(int(data["ep"]))
            except ValueError:
                await interaction.send(
                    f"Could not convert `{data['ep']}` to a number", ephemeral=True
                )
                return
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.defer()
            bot: "Bot" = interaction.bot
            # noinspection PyTypeChecker
            dt = list(map(lambda x: (x, points), self.participants))
            await bot.db.executemany(
                "INSERT INTO users (id, points) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET points = users.points + $2",
                dt,
            )
            await interaction.send("Successfully added points to all participants")

        await inter.response.send_modal(
            DataModal(
                "Enter Points",
                [disnake.ui.TextInput(label="Amount of EP", custom_id="ep")],
                modal_callback,
            )
        )

    @disnake.ui.button(
        label="Add Trophy to Participants", style=disnake.ButtonStyle.green, row=1
    )
    async def trophy_part(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        async def modal_callback(interaction: disnake.ModalInteraction):
            data = interaction.text_values
            bot: "Bot" = interaction.bot
            id = data["id"].strip().lower()
            trophy_exists = await bot.db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM trophies WHERE id = $1)", id
            )
            if not trophy_exists:
                await interaction.send(
                    f"Trophy with id `{id}` does not exist", ephemeral=True
                )
                return
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.defer()
            await bot.db.executemany(
                "INSERT INTO inventories (id, trophy_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [(i, id) for i in self.participants],
            )
            await interaction.send("Successfully added this trophy to all participants")

        await inter.response.send_modal(
            DataModal(
                "Enter Trophy ID",
                [
                    disnake.ui.TextInput(
                        label="trophy_id",
                        custom_id="id",
                        placeholder="event_participant_2022",
                        max_length=32,
                    )
                ],
                modal_callback,
            )
        )

    @disnake.ui.button(
        label="Add EP to Winners",
        style=disnake.ButtonStyle.green,
        row=2,
        custom_id="ep_winners",
        disabled=True,
    )
    async def ep_winners(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        async def modal_callback(interaction: disnake.ModalInteraction):
            data = interaction.text_values
            try:
                points = abs(int(data["ep"]))
            except ValueError:
                await interaction.send(
                    f"Could not convert `{data['ep']}` to a number", ephemeral=True
                )
                return
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.defer()
            bot: "Bot" = interaction.bot
            # noinspection PyTypeChecker
            dt = list(map(lambda x: (x, points), self.winners))
            await bot.db.executemany(
                "INSERT INTO users (id, points) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET points = users.points + $2",
                dt,
            )
            await interaction.send("Successfully added points to all winners")

        await inter.response.send_modal(
            DataModal(
                "Enter Points",
                [disnake.ui.TextInput(label="Amount of EP", custom_id="ep")],
                modal_callback,
            )
        )

    @disnake.ui.button(
        label="Add Trophy to Winners",
        style=disnake.ButtonStyle.green,
        row=2,
        custom_id="tr_winners",
        disabled=True,
    )
    async def tr_winners(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        async def modal_callback(interaction: disnake.ModalInteraction):
            data = interaction.text_values
            bot: "Bot" = interaction.bot
            id = data["id"].strip().lower()
            trophy_exists = await bot.db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM trophies WHERE id = $1)", id
            )
            if not trophy_exists:
                await interaction.send(
                    f"Trophy with id `{id}` does not exist", ephemeral=True
                )
                return
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.defer()
            await bot.db.executemany(
                "INSERT INTO inventories (id, trophy_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [(i, id) for i in self.winners],
            )
            await interaction.send("Successfully added this trophy to all winners")

        await inter.response.send_modal(
            DataModal(
                "Enter Trophy ID",
                [
                    disnake.ui.TextInput(
                        label="trophy_id",
                        custom_id="id",
                        placeholder="event_winner_2022",
                        max_length=32,
                    )
                ],
                modal_callback,
            )
        )

    # noinspection PyTypeChecker
    @disnake.ui.button(label="End Event", style=disnake.ButtonStyle.red, row=3)
    async def end_event(self, _, inter: disnake.MessageInteraction):
        await inter.message.delete()
        await inter.response.defer()
        bot: "Bot" = inter.bot
        await bot.db.executemany(
            "INSERT INTO users (id, total_events) VALUES ($1, 1) ON CONFLICT (id) DO UPDATE SET total_events = users.total_events + 1",
            [(x,) for x in self.participants],
        )
        await bot.db.execute(
            "UPDATE users SET won_events = won_events + 1 WHERE id = ANY($1::BIGINT[])",
            self.winners,
        )
        await inter.send(
            f"Event was ended. Please use `/removeevent` command for cleanup"
        )


class ConfirmationView(disnake.ui.View):
    def __init__(self, inter: disnake.Interaction):
        super().__init__()
        self.user_id = inter.user.id
        self.value: bool | None = None
        self.inter: disnake.Interaction = inter

    async def on_timeout(self) -> None:
        self.stop()

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if inter.author.id != self.user_id:
            await inter.send("This button is not for you", ephemeral=True)
            return False
        return True

    async def get_result(self) -> tuple[disnake.MessageInteraction, bool]:
        await self.wait()
        for item in self.children:
            item.disabled = True
        if self.value is None:
            raise asyncio.TimeoutError()
        return self.inter, self.value  # type: ignore

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.green)
    async def confirm(self, _, inter: disnake.MessageInteraction):
        self.value = True
        self.inter = inter
        self.stop()

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel(self, _, inter: disnake.MessageInteraction):
        self.value = False
        self.inter = inter
        self.stop()


class DataModal(disnake.ui.Modal):
    def __init__(self, title: str, components: list, coro: Callable):
        super().__init__(title=title, components=components)
        self._coro = coro

    async def callback(self, interaction: disnake.ModalInteraction, /) -> None:
        try:
            await self._coro(interaction)
        except ValueError:
            await interaction.send("Invalid data format", ephemeral=True)


class Modal(disnake.ui.Modal):
    """
    Modal class that waits for user to fill modal out then returns results.
    """

    _fut: asyncio.Future
    _inter: disnake.ModalInteraction

    async def on_timeout(self) -> None:
        self._fut.set_result(True)

    async def callback(self, interaction: disnake.ModalInteraction, /) -> None:
        # noinspection PyProtectedMember
        interaction._state._modal_store.remove_modal(
            interaction.author.id, interaction.custom_id
        )
        self._inter = interaction
        self._fut.set_result(False)

    async def wait(self) -> disnake.ModalInteraction:
        """
        Waits for user to fill modal out and returns resulting interaction.
        :return: Resulting ``ModalInteraction``.
        :raise ViewTimeout: Modal was timed out.
        """
        self._fut = asyncio.shield(asyncio.get_event_loop().create_future())
        if await self._fut:
            raise asyncio.TimeoutError()
        return self._inter
