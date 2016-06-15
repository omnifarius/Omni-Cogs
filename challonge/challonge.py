from .utils.dataIO import fileIO
from .utils import checks
import os
import discord
from discord.ext import commands
import asyncio

class Challonge:
    """Challonge API class!"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = fileIO("data/challonge/settings.json", "load")
        self.username = self.settings["username"]
        self.api_key = self.settings["api_key"]

    @commands.command()
    async def cot(self):
        """This does stuff!"""
        await self.bot.say("Soon, I'll be able to tell you about the current COT!")

    @commands.command()
    async def setuser(self):
        """This sets challonge username"""
        self.username = "LoonyBot"

    @commands.command()
    async def setapi(self):
        """This sets challonge API key"""
        self.api_key = "aQxII221PTVdHlsiYYEzvm2kYoNR8MMkOgplZni4"
    
def check_folders():
    if not os.path.exists("data/challonge"):
        print("Creating data/challonge folder...")
        os.makedirs("data/challonge")

def check_files():
    settings = {"username" : "LoonyBot", "api_key" : "aQxII221PTVdHlsiYYEzvm2kYoNR8MMkOgplZni4"}

    f = "data/challonge/settings.json"
    if not fileIO(f, "check"):
        print("Creating default challonge settings.json...")
        fileIO(f, "save", settings)
    else: #consistency check
        current = fileIO(f, "load")
        if current.keys() != settings.keys():
            for key in settings.keys():
                if key not in current.keys():
                    current[key] = settings[key]
                    print("Adding " + str(key) + " field to challonge settings.json")
            fileIO(f, "save", current)

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Challonge(bot))


