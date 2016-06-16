import discord
from discord.ext import commands
from cogs.utils import checks
from __main__ import settings


class Verify:
    """Custom Verify tool."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(no_pm=True, pass_context=True)
    async def verifyme(self, ctx, rolename: str="Verified", user: discord.Member=None):
        """Adds the specified role to the user"""
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.server
        role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(),
                                  ctx.message.server.roles)
        if user is None:
            user = author

        if role is None:
            await self.bot.say('Seomthing went wrong.  The "Verified" role cannot be fou
nd.')
            return

        if not channel.permissions_for(server.me).manage_roles:
            await self.bot.say('I don\'t have manage_roles permissions.')
            return

        await self.bot.add_roles(user, role)
        await self.bot.say('Added role {} to {}'.format(role.name, user.name))

def setup(bot):
    bot.add_cog(Verify(bot))


