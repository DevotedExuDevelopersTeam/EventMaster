import asyncpg
import disnake
from disnake.ext import commands

from utils.bot import Cog
from utils.image_generation import draw_profile_card


class EventProfile(Cog):
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.slash_command(name="profile", description="Display your or other user's event profile")
    async def profile(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member = None):
        await inter.response.defer()
        user = user or inter.author
        event_user = await self.bot.db.get_event_user(user.id).load()
        pic = await draw_profile_card(user, event_user)
        await inter.send(file=disnake.File(pic, "profile.png"))


class ProfileAdministration(Cog):
    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if not inter.user.guild_permissions.manage_guild:
            raise commands.MissingPermissions(["manage_guild"])
        return True

    @commands.slash_command(name="add_points", description="Adds event points to a person")
    async def add_points(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        points: int = commands.Param(ge=1, le=100000),
    ):
        await self.bot.db.get_event_user(user.id).update_event_points(points)
        await inter.send(f"Successfully added **{points}** to {user.mention}")

    @commands.slash_command(name="remove_points", description="Removes event points from a person")
    async def remove_points(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        points: int = commands.Param(ge=1, le=100000),
    ):
        try:
            await self.bot.db.get_event_user(user.id).update_event_points(-points)
            await inter.send(f"Successfully removed **{points}** from {user.mention}")
        except asyncpg.CheckViolationError:
            await inter.send("You cannot remove more points than user currently has", ephemeral=True)
