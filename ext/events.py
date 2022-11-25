import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path

import asyncpg
import disnake
from disnake.ext import commands, tasks

from utils.bot import Bot, Cog
from utils.views import EventEndView


class EventManagement(Cog):
    def __init__(self, bot: Bot):
        super().__init__(bot)
        self.groups_disabler.start()

    @tasks.loop(minutes=10)
    async def groups_disabler(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        data = await self.bot.db.fetchall(
            "SELECT role_id, event_id FROM groups WHERE start_time < $1 AND closed = FALSE",
            now,
        )
        self.bot.log.info("Got %d groups to close", len(data))
        event_data = {}
        for row in data:
            id = row["event_id"]
            if id not in event_data:
                event_data[id] = await self.bot.db.fetchrow(
                    "SELECT registration_channel_id AS channel_id, registration_message_id AS message_id FROM events WHERE id = $1",
                    id,
                )
            channel = self.bot.get_channel(event_data[id]["channel_id"])
            msg = await channel.fetch_message(event_data[id]["message_id"])
            view = disnake.ui.View.from_message(msg)
            for child in view.children:
                if isinstance(child, disnake.ui.Button) and child.custom_id.endswith(
                    str(row["role_id"])
                ):
                    child.disabled = True
                    await msg.edit(view=view)
                    self.bot.log.info("Group %s is no longer joinable", child.custom_id)
                    break

        await self.bot.db.execute(
            "UPDATE groups SET closed = TRUE WHERE start_time < $1", now
        )

    @Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id.startswith("gr-"):
            id = int(inter.component.custom_id[3:])
            await inter.user.add_roles(disnake.Object(id))
            await inter.send(
                f"Added <@&{id}> to {inter.author.mention}",
                allowed_mentions=disnake.AllowedMentions(roles=False),
                delete_after=3,
            )

    @commands.slash_command(name="newevent", description="Creates new event")
    async def newevent(
        self,
        inter: disnake.ApplicationCommandInteraction,
        name: str = commands.Param(max_length=16),
    ):
        await inter.response.defer()
        await inter.send(
            "Please add groups for event - send a sequence of UNIX timestamps separated by space in the following format:\n"
            "```1234567890 0987654321 6638572650\n```\nYou can get UNIX timestamp here: https://www.unixtimestamp.com/"
        )
        try:
            msg: disnake.Message = await self.bot.wait_for(
                "message", check=lambda m: m.author.id == inter.author.id, timeout=600
            )
            group_timestamps = list(map(int, msg.content.split()))
            if len(group_timestamps) > 10:
                group_timestamps = group_timestamps[:10]
            group_timestamps.sort()
        except asyncio.TimeoutError:
            await inter.send(f"{inter.author.mention} response timed out")
            return
        except ValueError:
            await inter.send("Invalid format, please use the command again.")
            return
        event_id = uuid.uuid4()
        await msg.delete()
        self.bot.log.info("%s started creation of event %s", inter.author, event_id.hex)
        await inter.send("Creating event, please wait...")

        await inter.edit_original_response("Creating roles...")
        groups = []
        roles = []
        for i, ts in enumerate(group_timestamps, 1):
            role = await inter.guild.create_role(
                name=f"{name} Event Participant G{i}".title()
            )
            groups.append((event_id, role.id, datetime.fromtimestamp(ts)))
            roles.append(role)

        await inter.edit_original_response("Creating channel...")
        overwrites = {
            inter.guild.default_role: disnake.PermissionOverwrite(
                read_messages=False, send_messages=False
            ),
            inter.guild.me: disnake.PermissionOverwrite(
                read_messages=True, send_messages=True
            ),
        }
        overwrites.update(
            {r: disnake.PermissionOverwrite(read_messages=False) for r in roles}
        )
        category = await inter.guild.create_category(f"{name.title()} Event")
        channel = await category.create_text_channel(
            f"{name.lower()}-registration", overwrites=overwrites
        )

        txt = (
            f"__**{name.title()} Event Registration**__\n"
            f"Please select a comfortable time for you to participate in event.\n"
            f"**YOU CAN SELECT THE GROUP ONLY ONCE**\n"
            f"{'-' * 20}\n"
        )
        view = disnake.ui.View()
        for i, (_, role_id, ts) in enumerate(groups, 1):
            view.add_item(
                disnake.ui.Button(label=f"Group {i}", custom_id=f"gr-{role_id}")
            )
            txt += f"**Group {i}:** {disnake.utils.format_dt(ts, 'f')}\n"
        msg = await channel.send(txt, view=view)

        await inter.edit_original_response("Registering event in database...")
        await self.bot.db.create_event(event_id, name, msg)
        await self.bot.db.create_groups(groups)

        await inter.delete_original_response()
        await inter.send(
            f"Successfully created **{name.title()} Event**. "
            f"Main registration channel is {channel.mention}, "
            f"please make sure to give everyone the permission "
            f"to view it when you open the registration."
        )

    @commands.slash_command(name="listevents", description="Lists current events")
    async def listevents(self, inter: disnake.ApplicationCommandInteraction):
        embed = disnake.Embed(color=0x00DDDD, title="Current Events")
        data = await self.bot.db.fetchall("SELECT id, name FROM events")
        for row in data:
            embed.add_field(name=row["name"], value=f"ID: {row['id'].hex}")

        await inter.send(embed=embed)

    @commands.slash_command(
        name="removeevent",
        description="Closes the event, removes all roles and channels created for event",
    )
    async def removeevent(self, inter: disnake.ApplicationCommandInteraction, id: str):
        id = uuid.UUID(id)
        exists = await self.bot.db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM events WHERE id = $1)", id
        )
        if not exists:
            await inter.send("Event with this ID does not exist", ephemeral=True)
            return
        self.bot.log.info("%s started deletion of event %s", inter.author, id.hex)
        await inter.send("Removing roles...")
        data = await self.bot.db.fetchall(
            "SELECT role_id FROM groups WHERE event_id = $1", id
        )
        for row in data:
            await inter.guild.get_role(row["role_id"]).delete()

        await inter.edit_original_response("Removing channel...")
        channel = self.bot.get_channel(
            await self.bot.db.fetchval(
                "SELECT registration_channel_id FROM events WHERE id = $1", id
            )
        )
        if len(channel.category.channels) == 1:
            await channel.category.delete()
        await channel.delete()

        await inter.edit_original_response("Cleaning up database...")
        await self.bot.db.execute("DELETE FROM events WHERE id = $1", id)

        await inter.delete_original_response()
        await inter.send("Removed the event successfully!")

    @commands.slash_command(
        name="endevent",
        description="Ends the event, gives out roles, EP and trophies. Use /removeevent for cleanup.",
    )
    async def endevent(self, inter: disnake.ApplicationCommandInteraction, id: str):
        id = uuid.UUID(id)
        exists = await self.bot.db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM events WHERE id = $1)", id
        )
        if not exists:
            await inter.send("Event with this ID does not exist", ephemeral=True)
            return
        data = await self.bot.db.fetchall(
            "SELECT role_id FROM groups WHERE event_id = $1", id
        )
        roles = [inter.guild.get_role(i["role_id"]) for i in data]
        participants = set()
        for role in roles:
            if role is None:
                continue
            participants |= set(map(lambda x: x.id, role.members))
        await inter.send(view=EventEndView(inter.author.id, list(participants)))


class TrophiesManagement(Cog):
    @commands.slash_command(name="create_trophy", description="Creates a new trophy")
    async def create_trophy(
        self,
        inter: disnake.ApplicationCommandInteraction,
        id: str = commands.Param(max_length=32),
        name: str = commands.Param(max_length=64),
        picture: disnake.Attachment = commands.Param(),
    ):
        await inter.response.defer()
        await picture.save(Path("data/trophies/", id + ".png"))
        try:
            await self.bot.db.create_trophy(id, name)
            await inter.send("Successfully created a new trophy!")
        except asyncpg.UniqueViolationError:
            await inter.send("Trophy with this id already exists.", ephemeral=True)

    @commands.slash_command(
        name="remove_trophy", description="Removes the specified trophy"
    )
    async def remove_trophy(
        self,
        inter: disnake.ApplicationCommandInteraction,
        id: str = commands.Param(max_length=32),
    ):
        await self.bot.db.remove_trophy(id)
        try:
            os.remove(Path("data/trophies/", id + ".png"))
        except FileNotFoundError:
            self.bot.log.warning("Failed to remove trophy image %s", id)
        await inter.send("The trophy was removed if it existed.")

    @commands.slash_command(
        name="give_trophy", description="Gives the trophy to a user"
    )
    async def give_trophy(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        trophy_id: str = commands.Param(max_length=32),
    ):
        try:
            await self.bot.db.give_trophy(user.id, trophy_id)
            await inter.send("Successfully gave the trophy to the user")
        except asyncpg.ForeignKeyViolationError:
            await inter.send("Invalid trophy ID", ephemeral=True)

    @commands.slash_command(
        name="take_trophy", description="Takes the trophy away from the user"
    )
    async def take_trophy(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        trophy_id: str = commands.Param(max_length=32),
    ):
        await self.bot.db.take_trophy(user.id, trophy_id)
        await inter.send("Removed the trophy from user if it existed.")
