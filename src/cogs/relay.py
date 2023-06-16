from nextcord import TextChannel, Message, RawReactionActionEvent, Emoji, PartialEmoji
from nextcord import slash_command, SlashOption
from nextcord.ext import commands
from nextcord.ext import application_checks
from tabulate import tabulate

from bot import RelayBot
from src.common.common import *


class Relay(commands.Cog):
    def __init__(self, bot: RelayBot):
        self.bot: RelayBot = bot
        self.pools: Dict[str, Dict[str, Union[Dict[str, Dict[str, Union[List[int], int]]], str]]] = {}

    async def init_analytics(self, pool_name: str, guild_id: int) -> None:
        """
        Initialize the analytics data for the specified pool and guild.

        :param pool_name: The name of the relay pool to initialize.
        :param guild_id: The ID of the guild for which the analytics data should be initialized.
        """
        if pool_name not in self.pools:
            self.pools[pool_name] = {"password": None, "servers": {}}

        str_guild_id = str(guild_id)

        if str_guild_id not in self.pools[pool_name]["servers"]:
            self.pools[pool_name]["servers"][str_guild_id] = {"channels": [], "message_count": 0}

        await self.save_pools()

    async def load_pools(self) -> None:
        """Load pools from the database."""
        pools = await db.pools.find_one({"_id": "pools"})
        if not pools:
            await db.pools.insert_one({"_id": "pools", "data": {}})
            pools = {"data": {}}
        self.pools = pools["data"]

    async def save_pools(self) -> None:
        """Save pools to the database."""
        await db.pools.update_one({"_id": "pools"}, {"$set": {"data": self.pools}})

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Load pools when the bot is ready."""
        await self.load_pools()

    @commands.Cog.listener()
    async def on_message(self, message: Message) -> None:
        """Relay messages between channels in the same pool."""
        for pool_name, pool_data in self.pools.items():
            str_guild_id = str(message.guild.id)  # Convert the guild_id to a string
            server_data = pool_data.get("servers", {}).get(str_guild_id)
            if server_data and message.channel.id in server_data["channels"]:
                try:
                    await self.relay_message(message, pool_name)
                except Exception as e:
                    print(f"Error relaying message: {e}")

    def get_pools_for_channel(self, channel_id: int) -> List[str]:
        pools = []
        for pool_name, pool_data in self.pools.items():
            for guild_id, server_data in pool_data["servers"].items():
                if channel_id in server_data["channels"]:
                    pools.append(pool_name)
                    break
        return pools

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        # Ignore reactions from the bot itself
        if payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        pools = self.get_pools_for_channel(channel.id)

        if not all((channel, pools, message)):
            return

        for pool in pools:
            await self.relay_reaction(pool, message, payload.emoji)

    async def relay_reaction(self, pool_name: str, message: Message, emoji: Union[Emoji, PartialEmoji, str]):
        print(f"Relaying {emoji} on pool {pool_name}")
        servers = self.pools[pool_name]["servers"]

        for guild_id, server_data in servers.items():
            for channel_id in server_data["channels"]:
                channel = self.bot.get_channel(channel_id)
                if channel and channel.id != message.channel.id:
                    history = await channel.history(limit=20).flatten()
                    for relayed_message in history:
                        if relayed_message.content == message.content:
                            existing_reaction = None
                            for reaction in relayed_message.reactions:
                                if reaction.emoji == emoji:
                                    existing_reaction = reaction
                                    break

                            if not existing_reaction:
                                await relayed_message.add_reaction(emoji)

    async def relay_message(self, message: Message, pool_name: str) -> None:
        """
        Relay a message to other channels in the same pool.

        :param message: The message object that needs to be relayed.
        :param pool_name: The name of the pool in which the message should be relayed.
        """

        # Ignore messages from the bot or other bots
        if message.author == self.bot.user or message.author.bot:
            return

        servers = self.pools[pool_name]["servers"]
        originating_guild_id = str(message.guild.id)

        message_relayed = False

        # Relay the message to the other channels in the pool
        for guild_id, server_data in servers.items():
            for channel_id in server_data["channels"]:
                if channel_id != message.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        webhook = await self.bot.find_or_create_webhook(channel, "RelayBot")
                        
                        # Check for any attachments in the message
                        files = []
                        for attachment in message.attachments:
                            file = await attachment.to_file()
                            files.append(file)

                        relayed_message = await webhook.send(
                            message.content,
                            username=f"{message.author.display_name} · {message.guild.name}",
                            avatar_url=message.author.avatar.url,
                            files=files,
                            wait=True
                        )

                        # Add reactions to the relayed message
                        for reaction in message.reactions:
                            try:
                                await relayed_message.add_reaction(reaction.emoji)
                            except Exception:
                                pass

                        message_relayed = True

        # Increment the message count only for the sending server
        if message_relayed:
            servers[originating_guild_id]["message_count"] += 1

        await self.save_pools()  # Save the updated pools

    @slash_command(
        name="set_password", description="Set a password for the relay pool."
    )
    async def set_password(
        self,
        inter: CustomInteraction,
        pool_name: str = SlashOption(
            description="The name of the pool to set the password for."
        ),
        password: str = SlashOption(description="The password for the pool."),
    ) -> None:
        if(inter.user.id == 770715610464124969):

            if pool_name not in self.pools:
                await inter.error(f"Pool `{pool_name}` does not exist.")
                return

            self.pools[pool_name]["password"] = password
            await self.save_pools()
            await inter.success(f"Password set for pool `{pool_name}`.", ephemeral=True)

        else:
            await inter.error("This command is reserved for Admins.")


    @slash_command(
        name="remove_password", description="Remove the password for a relay pool."
    )
    async def remove_password(
        self,
        inter: CustomInteraction,
        pool_name: str = SlashOption(
            description="The name of the pool to remove the password from."
        ),
    ) -> None:
        if(inter.user.id == 770715610464124969):

            if pool_name not in self.pools:
                await inter.error(f"Pool `{pool_name}` does not exist.")
                return

            if self.pools[pool_name]["password"] is None:
                await inter.error(f"Pool `{pool_name}` does not have a password.")
                return

            self.pools[pool_name]["password"] = ""
            await self.save_pools()
            await inter.success(f"Password removed for pool `{pool_name}`.", ephemeral=True)

        else:
            await inter.error("This command is reserved for Admins.")


    @slash_command(name="add_to_pool", description="Add a channel to the relay pool.")
    async def add_to_pool(
            self,
            inter: CustomInteraction,
            pool_name: str = SlashOption(
                description="The name of the pool to add the channel to."
            ),
            channel: Optional[TextChannel] = SlashOption(
                description="The channel to add to the relay pool."
            ),
            password: Optional[str] = SlashOption(
                description="The password for the pool, if required."
            ),
    ) -> None:
        if(inter.user.id == 770715610464124969):

            if not channel:
                channel = inter.channel

            guild_id = str(channel.guild.id)

            if pool_name not in self.pools:
                self.pools[pool_name] = {"password": password, "servers": {}}
                await self.save_pools()
                await inter.success(f"Pool `{pool_name}` created.", ephemeral=True)

            pool_data = self.pools[pool_name]
            pool_password = pool_data.get("password", None)

            if pool_password is not None and pool_password != password:
                if password:
                    await inter.error(f"Invalid password for pool `{pool_name}`.")
                else:
                    await inter.error(f"This pool requires a password.")
                return

            # Initialize the guild in the pool if it does not exist
            if guild_id not in pool_data["servers"]:
                pool_data["servers"][guild_id] = {"channels": [], "message_count": 0}

            pool_data["servers"][guild_id]["channels"].append(channel.id)
            await self.save_pools()
            await inter.success(
                f"Channel {channel.mention} added to the `{pool_name}` pool.",
                ephemeral=True,
            )
        else:
            await inter.error("This command is reserved for Admins.")



    @slash_command(
        name="remove_from_pool", description="Remove a channel from a relay pool."
    )
    async def remove_from_pool(
        self,
        inter: CustomInteraction,
        pool_name: str = SlashOption(
            description="The name of the pool to remove the channel from."
        ),
        channel: Optional[TextChannel] = SlashOption(
            description="The channel to remove from the relay pool."
        ),
    ) -> None:
        if(inter.user.id == 770715610464124969):

            if not channel:
                channel = inter.channel

            if pool_name not in self.pools:
                await inter.error(f"Pool `{pool_name}` does not exist.")
                return

            guild_id = str(channel.guild.id)

            if guild_id not in self.pools[pool_name]["servers"] or channel.id not in \
                    self.pools[pool_name]["servers"][guild_id]["channels"]:
                # Find pools the channel is in
                pools = [pool for pool, pool_data in self.pools.items() if
                        channel.id in pool_data["servers"].get(guild_id, {}).get("channels", [])]
                if pools:
                    pools_str = "`, `".join(pools)
                    await inter.error(
                        f"Channel {channel.mention} is not in the `{pool_name}` pool. "
                        f"Currently in: `{pools_str}`"
                    )
                else:
                    await inter.error(f"Channel {channel.mention} is not in any pool.")
                return

            self.pools[pool_name]["servers"][guild_id]["channels"].remove(channel.id)
            await self.save_pools()
            await inter.success(f"Channel {channel.mention} removed from the `{pool_name}` pool.", ephemeral=True)

        else:
            await inter.error("This command is reserved for Admins.")




    @slash_command(
        name="list_pools", description="List all relay pools and their channels."
    )
    async def list_pools(self, inter: CustomInteraction) -> None:

        if(inter.user.id == 770715610464124969):
            table_data = []

            for pool_name, pool_data in self.pools.items():
                for guild_id, server_data in pool_data["servers"].items():
                    for channel_id in server_data["channels"]:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            guild = channel.guild
                            table_data.append([pool_name, guild.name, "#" + channel.name])

            if not table_data:
                await inter.error("No relay pools found.")
                return

            table = tabulate(table_data, headers=["Pool", "Server", "Channel"])
            await inter.send(f"```\n{table}\n```")

        else:
            await inter.error("This command is reserved for Admins.")





    @slash_command(
        name="pool_analytics", description="Display analytics for relay pools."
    )
    async def pool_analytics(self, inter: CustomInteraction) -> None:

        if(inter.user.id == 770715610464124969):
            table_data = []

            for pool_name, pool_data in self.pools.items():
                servers = pool_data["servers"]
                for guild_id, server_data in servers.items():
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        table_data.append(
                            [pool_name, guild.name, server_data["message_count"]]
                        )

            if table_data:
                table = tabulate(table_data, headers=["Pool", "Server", "Message Count"])
                await inter.send(f"```\n{table}\n```")
            else:
                await inter.error("No analytics available.")
        else: 
            await inter.error("This command is reserved for Admins.")            



def setup(bot):
    bot.add_cog(Relay(bot))
