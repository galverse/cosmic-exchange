from json import loads
from typing import *
from urllib.parse import urlencode

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,  # noqa
)
from nextcord import (
    Color,
    Embed,
    Interaction,
    PartialInteractionMessage,
)
from nextcord.ext.commands import Context
from requests import post

DEFAULT_PREFIX: str = "!"

mg: AsyncIOMotorClient = AsyncIOMotorClient("localhost", 27017)
db: AsyncIOMotorDatabase = mg.GalverseRelay


class Emojis:
    """Emojis used in bot responses."""

    error = e = red = ""
    success = s = green = ""
    neutral = n = gray = ""
    waiting = w = typing_ = ""
    warning = yellow = ""


class Colours:
    """Colours used in bot responses."""

    error = r = red = Color(15742004)
    success = g = green = Color(3066993)
    neutral = n = normal = base = Color(0x212121)
    warn = y = yellow = Color(16707936)


class CustomInteraction(Interaction):
    """A custom Interaction class with additional methods."""

    def __init__(self, *args, **kwargs):
        self.bot = None

        super().__init__(*args, **kwargs)

    async def error(self, err: Union[str, Exception], ephemeral=True):
        """Send an error Embed to a specified channel."""

        if self.response.is_done():
            return await self.followup.send(
                embed=Embed(colour=Colours.error, description=f"{Emojis.error} {err}"),
                ephemeral=ephemeral,
            )
        else:
            return await self.response.send_message(
                embed=Embed(colour=Colours.error, description=f"{Emojis.error} {err}"),
                ephemeral=ephemeral,
            )

    async def success(self, string: str, ephemeral=True) -> PartialInteractionMessage:
        """Send a success Embed to a specified channel."""

        if self.response.is_done():
            m = await self.followup.send(
                embed=Embed(
                    colour=Colours.success, description=f"{Emojis.success} {string}"
                ),
                ephemeral=ephemeral,
            )
        else:
            m = await self.response.send_message(
                embed=Embed(
                    colour=Colours.success, description=f"{Emojis.success} {string}"
                ),
                ephemeral=ephemeral,
            )

        return m


class CustomContext(Context):
    """A custom Context class with additional methods."""

    async def error(self, err: Union[str, Exception], ping=None, to=None):
        """Send an error Embed to a specified channel."""
        to = to or self
        if ping:
            return await to.send(
                f"{ping.mention}",
                embed=Embed(colour=Colours.error, description=f"{Emojis.error} {err}"),
            )
        else:
            return await to.send(
                embed=Embed(colour=Colours.error, description=f"{Emojis.error} {err}")
            )

    async def success(self, string: str, ping=None, to=None) -> None:
        """Send a success Embed to a specified channel."""
        to = to or self
        if ping:
            await to.send(
                f"{ping.mention}",
                embed=Embed(
                    colour=Colours.success,
                    description="%s %s" % (Emojis.success, string),
                ),
            )
        else:
            await to.send(
                embed=Embed(
                    colour=Colours.success,
                    description="%s %s" % (Emojis.success, string),
                )
            )
