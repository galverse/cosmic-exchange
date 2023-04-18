from datetime import timedelta, datetime
from os import listdir
from os.path import splitext

from cooldowns import CallableOnCooldown
from nextcord import (
    Intents,
    AllowedMentions,
    InteractionResponded,
    ApplicationInvokeError,
    Webhook,
)
from nextcord.ext.commands import (
    CheckFailure,
    CommandNotFound,
    CommandInvokeError,
    AutoShardedBot,
    CommandOnCooldown,
)

from src.common.common import *


class RelayBot(AutoShardedBot):
    def __init__(self) -> None:
        # Make sure the bot can't be abused to mass ping
        allowed_mentions = AllowedMentions(roles=True, everyone=True, users=True)

        # Minimum required
        intents = Intents(
            members=True,
            guilds=True,
            emojis=True,
            messages=True,
            reactions=True,
            invites=True,
            guild_messages=True,
            message_content=True,
        )

        super().__init__(
            description="GalverseRelay",
            chunk_guilds_at_startup=True,
            heartbeat_timeout=150.0,
            allowed_mentions=allowed_mentions,
            intents=intents,
            owner_ids=[
                770715610464124969,  # Devin
            ],
            case_insensitive=True,
        )

    @staticmethod
    async def find_or_create_webhook(channel, webhook_name) -> Webhook:
        """
        Finds an existing webhook with the given name or creates a new one.

        :param channel: The channel to search for the webhook in.
        :param webhook_name: The name of the webhook to find or create.
        :return: The found or created webhook.
        """
        # Fetch the list of webhooks in the channel
        webhooks = await channel.webhooks()

        # Check if a webhook with the given name exists
        webhook = next((wh for wh in webhooks if wh.name == webhook_name), None)

        # If the webhook doesn't exist, create a new one
        if webhook is None:
            webhook = await channel.create_webhook(name=webhook_name)

        return webhook

    def get_interaction(self, data, *, cls=CustomInteraction) -> CustomInteraction:
        i = super().get_interaction(data, cls=cls)
        i.bot = self
        return i

    async def get_context(self, message, *, cls=CustomContext) -> CustomContext:
        """Use CustomContext instead of Context."""
        return await super().get_context(message, cls=cls)

    async def on_application_command_error(
        self, interaction: CustomInteraction, err: Exception
    ) -> None:
        """Catch and handle errors thrown by the bot."""
        try:
            if isinstance(err, ApplicationInvokeError):
                err = err.original
            if isinstance(err, CheckFailure):
                return
            elif isinstance(err, CommandNotFound):
                return  # Ignore
            elif isinstance(err, CallableOnCooldown):
                hours = int(err.retry_after) // 3600
                mins = (int(err.retry_after) // 60) - hours * 60
                secs = int(err.retry_after) % 60

                ts = int(
                    (
                        datetime.utcnow()
                        + timedelta(seconds=(secs + (mins * 60) + (hours * 3600)))
                    ).timestamp()
                )

                err = Exception(f"You're on cooldown. Try again <t:{ts}:R>.")
            elif isinstance(err, CommandOnCooldown):
                hours = int(err.retry_after) // 3600
                mins = (int(err.retry_after) // 60) - hours * 60
                secs = int(err.retry_after) % 60

                ts = int(
                    (
                        datetime.utcnow()
                        + timedelta(seconds=(secs + (mins * 60) + (hours * 3600)))
                    ).timestamp()
                )

                err = Exception(f"You're on cooldown. Try again <t:{ts}:R>.")
            elif isinstance(err, CommandInvokeError):
                # Try to simplify HTTP errors
                try:
                    err = Exception(getattr(err, "original").text or str(err))
                except AttributeError:
                    pass
            elif (
                isinstance(err, SyntaxError)
                or isinstance(err, ValueError)
                or isinstance(err, IndexError)
                or isinstance(err, TypeError)
                or isinstance(err, NameError)
            ):
                err = Exception(f"{type(err).__name__}: {err}")

            # Attempt to simplify error message
            msg = ""
            msg += str(getattr(err, "__cause__") or err)

            # Send the error to the user
            try:
                await interaction.error(msg)
            except InteractionResponded:
                await interaction.followup.send(
                    embed=Embed(
                        colour=Colours.error, description=f"{Emojis.error} {msg}"
                    ),
                    ephemeral=True,
                )
        except Exception:
            raise err

    async def on_ready(self) -> None:  # noqa
        await self.sync_all_application_commands()
        print("Ready")


if __name__ == "__main__":
    bot = RelayBot()

    # Remove the default help command so a better one can be added
    bot.remove_command("help")

    # Load cogs
    # Ignores files starting with "_", like __init__.py
    for cog in listdir("./src/cogs/"):
        if not cog.startswith("_"):
            file_name, file_extension = splitext(cog)
            bot.load_extension("src.cogs.%s" % file_name)

    # Code written after this block may not run
    with open("./data/token.txt", "r") as token:
        bot.run(token.readline())
