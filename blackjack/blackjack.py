import discord
from discord.ext import commands
from .utils.dataIO import fileIO
from .utils import checks
from __main__ import send_cmd_help
import os
import logging
from random import randint
import datetime
import time
import random
import asyncio


class Blackjack:
    """Blackjack

    A module for betting against the house!"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = fileIO("data/blackjack/settings.json", "load") 
        self.bank = fileIO("data/blackjack/bank.json", "load")
        self.activeUsers = {}
        self.currentUser = {}
        self.bj_sessions = []
        self.payday_register = {}
        self.blackjack_register = {}
        self.subcommands = ["register", "payday", "leaders", "transfer", "balance", "sessions"]

    @commands.group(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def blackjackset(self, ctx):
        """Changes Blackjack module settings"""
        if ctx.invoked_subcommand is None:
            msg = "```"
            for k, v in self.settings.items():
                msg += str(k) + ": " + str(v) + "\n"
            msg += "\nType {}help blackjackset to see the list of commands.```".format(ctx.prefix)
            await self.bot.say(msg)

    @blackjackset.command(name="timeout", pass_context=True)
    async def timeout(self, ctx, seconds : int):
        """Seconds until blackjack is considered inactive.
        """
        if seconds <= 30:
            await self.bot.say("Timeout interval must be more than 30")
            return
        self.settings["ACTIVE_TIMEOUT"] = seconds
        await self.bot.say("Blackjack activity timeout is now: " + str(self.settings["ACTIVE_TIMEOUT"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)

    @blackjackset.command(name="bettime", pass_context=True)
    async def bettime(self, ctx, seconds : int):
        """Seconds between first bet and starting the deal.
        """
        if seconds <= 5:
            await self.bot.say("Bet timeout interval must be more than 5")
            return
        self.settings["BET_TIMEOUT"] = seconds
        await self.bot.say("Blackjack bet timeout is now: " + str(self.settings["BET_TIMEOUT"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)

    @blackjackset.command(name="delay", pass_context=True)
    async def delay(self, ctx, seconds : int):
        """Seconds until user times out.
        """
        if seconds <= 10:
            await self.bot.say("Activity delay must be more than 10")
            return
        self.settings["ACTIVE_DELAY"] = seconds
        await self.bot.say("Active user delay is now: " + str(self.settings["ACTIVE_DELAY"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)


    @blackjackset.command(name="minbet", pass_context=True)
    async def minbet(self, ctx, minbet : int):
        """Minimum bet.
        """
        if minbet <= 0:
            await self.bot.say("Minmum bet must be more than 0!")
            return
        self.settings["MIN_BET"] = minbet
        await self.bot.say("Minimum blackjack bet is now: " + str(self.settings["MIN_BET"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)

    @blackjackset.command(name="maxbet", pass_context=True)
    async def maxbet(self, ctx, maxbet : int):
        """Maximum bet.
        """
        minbet = self.settings["MIN_BET"]
        if maxbet < 100:
            await self.bot.say("Maximum bet must be more than 100!")
            return
        if maxbet < minbet:
            await self.bot.say("Maximum bet must be higher than the minimum!")
            return
        self.settings["MAX_BET"] = maxbet
        await self.bot.say("Maximum blackjack bet is now: " + str(self.settings["MAX_BET"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)


    @blackjackset.command(name="paydaytime", pass_context=True)
    async def paydaytime(self, seconds : int):
        """Seconds between each payday"""
        self.settings["PAYDAY_TIME"] = seconds
        await self.bot.say("Value modified. At least " + str(seconds) + " seconds must pass between each payday.")
        fileIO("data/blackjack/settings.json", "save", self.settings)


    @blackjackset.command(name="paydaycredits", pass_context=True)
    async def paydaycredits(self, credits : int):
        """Credits earned each payday"""
        self.settings["PAYDAY_CREDITS"] = credits
        await self.bot.say("Every payday will now give " + str(credits) + " credits.")
        fileIO("data/blackjack/settings.json", "save", self.settings)


    @commands.group(name="blackjack", pass_context=True)
    async def _blackjack(self, ctx):
        """Play Blackjack!!

        Step 1:  Register your blackjack account using !blackjack register
        Step 2:  Start a game using !blackjack start.  If one is already running, join the fun!
        Step 3:  Place a !bet at the table and follow dealer instructions from there.  
        Step 4:  If you run out of money, get a !blackjack payday"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_blackjack.command(pass_context=True)
    async def start(self, ctx):
        """Starts a blackjack table!"""
        message = ctx.message
        #Check for session, start if there isn't one
        if not await get_bj_by_channel(message.channel):
            b = BlackjackSession(message, self.settings)
            self.bj_sessions.append(b)
            await b.dealer_waiting()
        else:
            await self.bot.say("A blackjack table is already started in this channel.")
    
    @_blackjack.command(pass_context=True)    
    @checks.mod_or_permissions(manage_server=True)
    async def stop(self, ctx):
        """Stops the current channel's blackjack table"""
        message = ctx.message
        if await get_bj_by_channel(message.channel):
            s = await get_bj_by_channel(message.channel)
            s.status = "stopping"
            s.stop = True
            await self.bot.say("Blackjack stopping...")
        else:
            await self.bot.say("There's no blackjack table started in this channel.")

    @_blackjack.command(pass_context=True)
    async def sessions(self):
        """Displays the number of sessions"""
        sessions = len(self.bj_sessions)
        await self.bot.say("Sessions: "+str(sessions))
        channels = []
        for sess in self.bj_sessions:
            channels.append(str(sess.channel))
        print(channels)


    @_blackjack.command(pass_context=True, no_pm=True)
    async def register(self, ctx):
        """Registers an account at the Blackjack tables.
        """
        user = ctx.message.author
        if user.id not in self.bank:
            self.bank[user.id] = {"name" : user.name, "balance" : 1000}
            fileIO("data/blackjack/bank.json", "save", self.bank)
            await self.bot.say("{} Blackjack account opened. Current balance: {}".format(user.mention, str(self.check_balance(user.id))))
        else:
            await self.bot.say("{} You already have an account at the Blackjack tables.".format(user.mention))

    @_blackjack.command(pass_context=True)
    async def balance(self, ctx, user : discord.Member=None):
        """Shows balance of user.
        Defaults to yours."""
        if not user:
            user = ctx.message.author
            if self.account_check(user.id):
                await self.bot.say("{} Your Blackjack table balance is: {}".format(user.mention, str(self.check_balance(user.id))))
            else:
                await self.bot.say("{} You don't have an account at the Blackjack tables. Type {}blackjack register to open one.".format(user.mention, ctx.prefix))
        else:
            if self.account_check(user.id):
                balance = self.check_balance(user.id)
                await self.bot.say("{}'s Blackjack table balance is {}".format(user.name, str(balance)))
            else:
                await self.bot.say("That user has no Blackjack table account yet.")

    @_blackjack.command(pass_context=True, no_pm=True)
    async def payday(self, ctx):
        """Get some free blackjack table credits"""
        author = ctx.message.author
        id = author.id
        if self.account_check(id):
            if id in self.payday_register:
                seconds = abs(self.payday_register[id] - int(time.perf_counter()))
                if seconds  >= self.settings["PAYDAY_TIME"]:
                    self.add_money(id, self.settings["PAYDAY_CREDITS"])
                    self.payday_register[id] = int(time.perf_counter())
                    await self.bot.say("{} Here, take some Blackjack table credits. Enjoy! (+{} credits!)".format(author.mention, str(self.settings["PAYDAY_CREDITS"])))
                else:
                    await self.bot.say("{} Too soon. For your next Blackjack payday, you have to wait {}.".format(author.mention, self.display_time(self.settings["PAYDAY_TIME"] - seconds)))
            else:
                self.payday_register[id] = int(time.perf_counter())
                self.add_money(id, self.settings["PAYDAY_CREDITS"])
                await self.bot.say("{} Here, take some credits. Enjoy! (+{} credits!)".format(author.mention, str(self.settings["PAYDAY_CREDITS"])))
        else:
            await self.bot.say("{} You need a blackjack account to receive credits. Type {}blackjack register to open one.".format(author.mention, ctx.prefix))

    @_blackjack.command(pass_context=True)
    async def transfer(self, ctx, user : discord.Member, sum : int):
        """Transfer blackjack credits to other users"""
        author = ctx.message.author
        if author == user:
            await self.bot.say("You can't transfer money to yourself.")
            return
        if sum < 1:
            await self.bot.say("You need to transfer at least 1 credit.")
            return
        if self.account_check(user.id):
            if self.enough_money(author.id, sum):
                self.withdraw_money(author.id, sum)
                self.add_money(user.id, sum)
                logger.info("{}({}) transferred {} blackjack credits to {}({})".format(author.name, author.id, str(sum), user.name, user.id))
                await self.bot.say("{} credits have been transferred to {}'s blackjack account.".format(str(sum), user.name))
            else:
                await self.bot.say("You don't have that sum in your blackjack account.")
        else:
            await self.bot.say("That user has no blackjack account.")

    @_blackjack.command()
    async def leaders(self, top : int=10):
        """Prints the blackjack credit leaders!
        Defaults to the Top Ten"""
        if top < 1:
            top = 10
        bank_sorted = sorted(self.bank.items(), key=lambda x: x[1]["balance"], reverse=True)
        if len(bank_sorted) < top:
            top = len(bank_sorted)
        topten = bank_sorted[:top]
        highscore = ""
        place = 1
        for id in topten:
            highscore += str(place).ljust(len(str(top))+1)
            highscore += (id[1]["name"]+" ").ljust(23-len(str(id[1]["balance"])))
            highscore += str(id[1]["balance"]) + "\n"
            place += 1
        if highscore:
            if len(highscore) < 1985:
                await self.bot.say("```py\n"+highscore+"```")
            else:
                await self.bot.say("That's too many blackjack leaders to be displayed. Try with a lower <top> parameter.")
        else:
            await self.bot.say("There are no accounts in the blackjack bank.")

    @commands.command(pass_context=True, no_pm=True)
    async def bet(self, ctx, bet : int):
        """Place a bet against the dealer.
        """
        message = ctx.message
        if await get_bj_by_channel(message.channel):
                session = await get_bj_by_channel(message.channel)
                print("Active table found.  Checking bet...")
        else:
            await self.bot.say("Perhaps you should start a table first...")
            return
        #session should now be the active channel's session
        author = ctx.message.author
        if not self.account_check(author.id):
            await self.bot.say("{} You need an account to play blackjack. Type {}blackjack register to open one.".format(author.mention, ctx.prefix))
            return
        if self.enough_money(author.id, bet):
            if bet >= self.settings["MIN_BET"] and bet <= self.settings["MAX_BET"]:
                if session.status == "awaiting bets" or session.status == "active bets":  
                    #if not author.id in self.blackjack_register:
                    #    self.blackjack_register[author.id] = int(time.perf_counter())
                    session.status = "active bets"
                    await self.bot.say("Bet {2} accepted, dealing soon.  {0}'s balance is: {1}".format(author.name, str(self.check_balance(author.id)), str(bet)))
                    session.bets[author] = bet
                    session.betReady = True
                else:
                    await self.bot.say("Sorry, {}, but please wait until I'm accepting bets!".format(author.mention))
                return
            else:
                await self.bot.say("{0} Bid must be between {1} and {2}.".format(author.mention, self.settings["MIN_BET"], self.settings["MAX_BET"]))
        else:
            await self.bot.say("{0} You need an account with enough funds to play the blackjack table.".format(author.mention))

    def account_check(self, id):
        if id in self.bank:
            return True
        else:
            return False

    def check_balance(self, id):
        if self.account_check(id):
            return self.bank[id]["balance"]
        else:
            return False

    def add_money(self, id, amount):
        if self.account_check(id):
            self.bank[id]["balance"] = self.bank[id]["balance"] + int(amount)
            fileIO("data/blackjack/bank.json", "save", self.bank)
        else:
            return False

    def withdraw_money(self, id, amount):
        if self.account_check(id):
            if self.bank[id]["balance"] >= int(amount):
                self.bank[id]["balance"] = self.bank[id]["balance"] - int(amount)
                fileIO("data/blackjack/bank.json", "save", self.bank)
            else:
                return False
        else:
            return False

    def enough_money(self, id, amount):
        if self.account_check(id):
            if self.bank[id]["balance"] >= int(amount):
                return True
            else:
                return False
        else:
            return False

    def set_money(self, id, amount):
        if self.account_check(id):
            self.bank[id]["balance"] = amount
            fileIO("data/blackjack/bank.json", "save", self.bank)
            return True
        else:
            return False

    def display_time(self, seconds, granularity=2): # What would I ever do without stackoverflow?
        intervals = (                               # Source: http://stackoverflow.com/a/24542445
            ('weeks', 604800),  # 60 * 60 * 24 * 7
            ('days', 86400),    # 60 * 60 * 24
            ('hours', 3600),    # 60 * 60
            ('minutes', 60),
            ('seconds', 1),
            )

        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(value, name))
        return ', '.join(result[:granularity])


class BlackjackSession():
    def __init__(self, message, settings):
        self.channel = message.channel
        self.settings = settings
        self.cardranks = [":zero:", ":a:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:", ":ten:", ":ten:", ":ten:", ":ten:"]
        self.cardsuits = [":clubs:", ":diamonds:", ":hearts:", ":spades:"]
        self.commands = ["hit", "stand", "stay", "double", "split", "surrender"]
        self.stop = False
        self.dealerReady = True
        self.betReady = False
        self.status = None
        self.timer = None
        self.bettimer = None
        self.count = 0
        self.pbjcount = 0 #player blackjacks
        self.dbjcount = 0 #dealer blackjacks
        self.bets = {} #[user]bet
        self.hands = {} #[user]Hand
        self.blackjacks = [] #[user]
        self.deck = Deck()
        self.activeUser = None

    async def check_command(self, message):
        #print("active user: " + str(self.activeUser))
        foundcom = False
        if message.author == self.activeUser:
            if message.author.id != bj_manager.bot.user.id:
                for com in self.commands:
                    if com in message.content.lower():
                        foundcom = True
                        if com == "hit":  self.status = "hitting"
                        if com == "stay":  self.status = "standing"
                        if com == "stand":  self.status = "standing"
                        if com == "split":  self.status = "splitting"
                        if com == "double":  self.status = "doubling"
                        if com == "surrender":  self.status = "surrendering"
                        return True
        #add a "confused" status if more than one command present
        #print(message.content)

    async def dealer_waiting(self):
        """Bulk of the while loop for the dealer wait period"""
        self.status = "awaiting bets"
        self.timer = int(time.perf_counter())        
        await bj_manager.bot.change_status(discord.Game(name="Blackjack"))
        while not self.stop and abs(self.timer - int(time.perf_counter())) <= self.settings["ACTIVE_TIMEOUT"]:
            if self.dealerReady: await bj_manager.bot.say("Dealer Ready!  Place your !bet now please.")
            self.dealerReady = False
            print(self.status + "... Timer: " + str(abs(self.timer - int(time.perf_counter()))))
            await asyncio.sleep(1)
            if self.status == "active bets":
                self.status == "dealing"
                print("Bets found, let's start bet cooldown timer")
                self.bettimer = int(time.perf_counter())
                self.betReady = True
                while abs(self.bettimer - int(time.perf_counter())) <= self.settings["BET_TIMEOUT"]:
                    if self.betReady: 
                        endtime = self.settings["BET_TIMEOUT"] - abs(self.bettimer - int(time.perf_counter()))
                        await bj_manager.bot.say("Betting ends in {} seconds".format(str(endtime)))
                        self.betReady = False
                    print(self.status + "... Bet Timer: " + str(abs(self.bettimer - int(time.perf_counter()))))
                    await asyncio.sleep(1)
                print("Cooldown complete, let's play!!")
                await self.init_deal()
            elif self.stop:
                await self.stop_bj()
        print("Escaped the dealer_waiting while loop")
        if not self.stop:
            print("TIMEOUT reached, stopping...")
            await bj_manager.bot.say("Sorry, you took too long to bet!  Closing table.")
            await self.stop_bj()
        
    async def active_dealer(self):
        """Bulk of the while loop for the active dealer loop"""
        print(self.status + " --- " + self.activeUser.name + "'s turn")
        self.timer = int(time.perf_counter()) #reset timer
        while not self.stop and abs(self.timer - int(time.perf_counter())) <= self.settings["ACTIVE_DELAY"]:
            if abs(self.timer - int(time.perf_counter())) == self.settings["ACTIVE_DELAY"]:
                await bj_manager.bot.say("{} timed out.".format(self.activeUser.name))
                self.status = "standing"
            if self.status == "hitting":
                print("HITTING in the active_dealer loop")
                await self.do_hit(self.activeUser)
                #change self.status in do_hit accordingly
            elif self.status == "standing":
                print("STANDING in the active_dealer loop")
                await bj_manager.bot.say("{} stands.".format(self.activeUser.name))
                self.timer -= self.settings["ACTIVE_DELAY"]
                self.status = "dealing"
            elif self.status == "doubling":
                print("DOUBLING in the active_dealer loop")
                if len(self.hands[self.activeUser]) == 2:
                    if bj_manager.enough_money(self.activeUser.id, self.bets[self.activeUser]*2):
                        self.bets[self.activeUser] *= 2
                        await self.do_hit(self.activeUser)
                        self.timer -= self.settings["ACTIVE_DELAY"]
                    else: 
                        await bj_manager.bot.say("Not enough funds, you can just hit instead")
                else:
                    await bj_manager.bot.say("Sorry, but you can only double down on your initial two card hand.  Try hitting.")
                self.status = "dealing"
            elif self.status == "splitting":
                await bj_manager.bot.say("You'd like to split wouldn't you?!  Too bad I haven't been taught how to do that yet. Dealing is hard!")
                self.status = "dealing"
            elif self.status == "surrendering":
                print("SURRENDERING in active_dealer loop")
                if len(self.hands[self.activeUser]) == 2:
                    await bj_manager.bot.say("{} surrenders and gets half their bet back.".format(self.activeUser.name))
                    self.bets[self.activeUser] *= -0.5
                    self.timer -= self.settings["ACTIVE_DELAY"]
                else:
                    await bj_manager.bot.say("Sorry, but you can only surrender your initial hand.")
                self.status = "dealing"
            print(self.status + "... timer: " + str(abs(self.timer - int(time.perf_counter()))))
            await asyncio.sleep(1) #Waiting for a command or for the time limit
        print("Escaped the active dealer loop with status: " + self.status)
        self.status = "dealing"
        
    async def do_hit(self, hittingUser):
        """Hit function for players"""
        print("{} is hitting".format(hittingUser.name))
        newcard = self.deck.pop_card()
        self.hands[hittingUser].append(newcard)
        await self.print_hand(hittingUser, False)
        self.timer = int(time.perf_counter())
        newval = await self.value_hand(hittingUser)
        self.status = "dealing"
        if newval["high"] > 21:
            await bj_manager.bot.say("{0} busted with {1}".format(hittingUser.name, str(newval["high"])))
            print("{0} busted with {1}".format(hittingUser.name, str(newval["high"])))
            self.bets[hittingUser] *= -1
            self.timer -= self.settings["ACTIVE_DELAY"]
        elif newval["high"] == 21:
            self.status = "standing"

    async def finish_deal(self):
        """Finalize the dealer's hand actions"""
        self.status = "finishing"
        await bj_manager.bot.say("Revealing Dealer's hand:")
        await self.print_hand(bj_manager.bot.user, False)
        print("Finishing deal.  Hands left to check: " + str(len(self.hands)))
        for better in self.bets:
            if self.bets[better] <= 0:
                self.hands.pop(better, None)
                print("Removing {}'s hand from self.hands because they lost or surrendered".format(better.name))
        print("num blackjacks: " + str(len(self.blackjacks)))
        for luckybastard in self.blackjacks:
            print(luckybastard.name)
            self.hands.pop(luckybastard, None)
            print("Removing {}'s hand from self.hands because they already won with blackjack".format(luckybastard.name))
        print("Finishing deal.  Hands left to check: " + str(len(self.hands)))
        if len(self.hands) > 1:  #the "1" being the dealer's hand
            print("Process Dealer's hand since there are still active hands on table")
            dealervals = {}
            dealervals = await self.value_hand(bj_manager.bot.user)
            suspensetimer = int(time.perf_counter())
            while dealervals["high"] < 21 and abs(suspensetimer - int(time.perf_counter())) <= 20:
                print(self.status + "... Timer: " + str(abs(suspensetimer - int(time.perf_counter()))))                
                await asyncio.sleep(2) #Waiting for suspense!
                #print("Dealer val at top of while " + str(dealervals["high"]))
                if dealervals["high"] >= 17 and dealervals["high"] <= 21:
                    print("Dealer stands at " + str(dealervals["high"]))
                    await bj_manager.bot.say("Dealer stands at " + str(dealervals["high"]))
                    suspensetimer -= 20
                if dealervals["high"] < 17:
                    print("Dealer hits")
                    await bj_manager.bot.say("Dealer hits.")
                    newcard = self.deck.pop_card()
                    self.hands[bj_manager.bot.user].append(newcard)
                    dealervals = await self.value_hand(bj_manager.bot.user)
                    await self.print_hand(bj_manager.bot.user, False)
            #print("Dealer val after while " + str(dealervals["high"]))
            if dealervals["high"] > 21:
                await bj_manager.bot.say("Dealer busts with " + str(dealervals["high"]) + ".  Everyone's a winner!  Unless you busted...sucker.")
                print("Dealer BUST, everyone remaining wins!")
            else:
                for player in self.hands: #check who won!
                    print("checking player bet for: ".format(player))
                    if player != bj_manager.bot.user:
                        playervals = await self.value_hand(player)
                        if dealervals["high"] > playervals["high"]:
                            print("LOSER: " + str(player.name))
                            await bj_manager.bot.say("Sorry, {0}, but you lose with {1}!".format(player.mention, str(playervals["high"])))
                            self.bets[player] *= -1
                        if playervals["high"] > dealervals["high"]:
                            print("WINNER: " + str(player.name))
                            await bj_manager.bot.say("Congrats, {0}, you win with {1}!".format(player.mention, str(playervals["high"])))
                        if dealervals["high"] == playervals["high"]:
                            print("PUSH for " + str(player.name))
                            await bj_manager.bot.say("Push at {1}, take back your bet, {0}".format(player.mention, str(playervals["high"])))
                            self.bets[player] = 0
                print("No more bets to check...")
        else:
            print("Skipped processing since no players left to compare")
            if len(self.blackjacks) == 0:
                await bj_manager.bot.say("Sorry table, looks like the house won this round!")
            else:
                await bj_manager.bot.say("Nice blackjacks, but the rest of you are losers!")
        
        await self.analyze_bets()

    async def reset_dealer(self):
        """Reset globals and start fresh!"""
        print("===== Resetting to defaults =====")
        self.count += 1 #hands played per session
        self.activeUser = None
        self.deck = Deck()
        self.hands = {}
        self.bets = {}
        self.blackjacks = []
        self.timer = int(time.perf_counter())
        self.bettimer = None
        self.status = "awaiting bets"
        self.dealerReady = True
        self.betReady = False

    async def init_deal(self):
        """Deal the table some cards.
        """
        await bj_manager.bot.say("Shuffling and dealing...")
        self.deck.shuffle() #needs new deck here????
        #print(self.deck)
        fakehand = Hand('fake', False)
        self.deck.move_cards(fakehand, 2)
        print(fakehand)
        #print(str(fakehand.bjlowval) + " " + str(fakehand.bjhighval))
        fakedeal = Hand(bj_manager.bot.user.name, True)
        self.deck.move_cards(fakedeal, 2)
        print(fakedeal)
        fakedeal.isDealer = False
        print(fakedeal)
        #print(self.deck)
        for player in self.bets:
            print("active bet: " + player.name + str(self.bets[player]))
            playerhand = []
            playerhand.append(self.deck.pop_card())
            playerhand.append(self.deck.pop_card())
            self.hands[player] = playerhand
        dealerhand = []
        dealerhand.append(self.deck.pop_card())
        dealerhand.append(self.deck.pop_card())
        self.hands[bj_manager.bot.user] = dealerhand
        await self.print_hand(bj_manager.bot.user, True)
        #print(self.deck)
        for player in self.hands:
            if player != bj_manager.bot.user:
                await self.print_hand(player, False)
        #check for dealer BJ
        #offer insurance here eventually?
        if await self.hasBlackjack(bj_manager.bot.user):
            print("Dealer Blackjack!!!")
            self.dbjcount += 1
            await bj_manager.bot.say("Dealer Blackjack!!!")
            await self.print_hand(bj_manager.bot.user, False)
            for user in self.bets:
                if await self.hasBlackjack(user): #at least you didn't lose money
                    self.bets[user] = 0
                    await bj_manager.bot.say("Push for {}".format(user.mention))
                else: 
                    await bj_manager.bot.say("Sorry {}.  You lose".format(user.mention))
                    self.bets[user] = self.bets[user] * -1
            await self.analyze_bets()
        else:
            self.status = "dealing"
            firstPlayer = True
            for player in self.hands:
                if player.id != bj_manager.bot.user.id:
                    print(player.name + " in init_deal")
                    if await self.hasBlackjack(player):
                        self.bets[player] *= 2
                        await bj_manager.bot.say("BLACKJACK!  Congrats, {}.".format(player.mention))  
                        print("BLACKJACK for " + player.name)
                        self.pbjcount += 1
                        self.blackjacks.append(player)
                    else:
                        if not firstPlayer:
                            print("Not first player, so repriting hands...")
                            await self.print_hand(bj_manager.bot.user, True)
                            await self.print_hand(player, False)
                        firstPlayer = False
                        await bj_manager.bot.say("{}, you're up!  What action would you like to perform now?".format(player.mention))
                        self.activeUser = player
                        await self.active_dealer()
            self.activeUser = bj_manager.bot.user
            await self.finish_deal()


    async def analyze_bets(self):
        """Finalize bets and adjust the blackjack bank!"""
        print("Analyzing bets!")
        for player in self.bets:
            #deposit positive values and remove negative values
            print(player.name + " " + str(self.bets[player]))
            if self.bets[player] != 0:
                bj_manager.add_money(player.id, self.bets[player])
            await bj_manager.bot.say("{0}, your new blackjack balance is: {1}".format(player.mention, str(bj_manager.check_balance(player.id))))
        await self.reset_dealer()

    async def print_hand(self, player, isDealer):
        """Prints the hand[] list nice and pretty"""
        value = 0
        value_str = ''
        output = '' 
        hasAce = False
        hideFirst = True
        hand = self.hands[player]
        for card in hand:
            if card.rank == 1:
                hasAce = True
            if isDealer and hideFirst:
                output += ":question: :question: "
                hideFirst = False
            else:
                if card.rank > 10:
                    value += 10
                else:
                    value += card.rank
                output += self.cardranks[card.rank] + " " + self.cardsuits[card.suit] + " "
        value_str = str(value)
        total_str = " Total: "
        if hasAce == True and value <=11:
            value_str = str(value) + "/" + str(value+10)
        if isDealer:
            total_str = " Showing: "
        output = player.name + "'s hand: " + output + total_str + value_str
        print(output)
        await bj_manager.bot.say(output)
        
    async def hasBlackjack(self, player):
        """Returns True if hand is a blackjack"""
        print("Checking for blackjack")
        hand = self.hands[player]
        if len(hand) != 2: return False
        else:
            values = await self.value_hand(player)
            if values["high"] == 21: return True
            else: return False

    async def value_hand(self, player):
        """Values hand as a two part dict low/high to deal with Aces"""
        hand = self.hands[player]
        value = 0
        values = {}
        hasAce = False
        for card in hand: 
            if card.rank > 10:
                value += 10
            else:
                value += card.rank
            #print(str(value))
            if card.rank == 1:
                hasAce = True
        values["low"] = value
        if hasAce:
            if (value + 10) <= 21:
                values["high"] = value + 10
            else:
                values["high"] = value
        else:
            values["high"] = value
        print(player.name + " value: " + str(values["low"]) + " " + str(values["high"]))
        return values

    async def stop_bj(self):
        print("Ending blackjack session gracefully...")
        output = "Blackjack ended.\nSession Stats:\nHands played: "
        output += str(self.count)
        output += "\nPlayer blackjacks:"
        output += str(self.pbjcount)
        output += "\nDealer blackjacks:"
        output += str(self.dbjcount)
        print(output)
        await bj_manager.bot.change_status(None)
        await bj_manager.bot.say(output)
        bj_manager.bj_sessions.remove(self)


async def get_bj_by_channel(channel):
        for b in bj_manager.bj_sessions:
            if b.channel == channel:
                return b
        return False        

async def check_messages(message):
    if message.author.id != bj_manager.bot.user.id:
        if await get_bj_by_channel(message.channel):
            bjsession = await get_bj_by_channel(message.channel)
            await bjsession.check_command(message)

def check_folders():
    if not os.path.exists("data/blackjack"):
        print("Creating data/blackjack folder...")
        os.makedirs("data/blackjack")

def check_files():
    settings = {"ACTIVE_TIMEOUT" : 45, "MIN_BET" : 10, "MAX_BET" : 1000, "DECKS" : 1, "PAYDAY_CREDITS" : 1000, "PAYDAY_TIME" : 300, "ACTIVE_DELAY" : 20, "BET_TIMEOUT" : 10}

    f = "data/blackjack/settings.json"
    if not fileIO(f, "check"):
        print("Creating default blackjack's settings.json...")
        fileIO(f, "save", settings)
    else: #consistency check
        current = fileIO(f, "load")
        if current.keys() != settings.keys():
            for key in settings.keys():
                if key not in current.keys():
                    current[key] = settings[key]
                    print("Adding " + str(key) + " field to economy settings.json")
            fileIO(f, "save", current)

    f = "data/blackjack/bank.json"
    if not fileIO(f, "check"):
        print("Creating empty bank.json...")
        fileIO(f, "save", {})


def setup(bot):
    global logger
    global bj_manager
    check_folders()
    check_files()
    logger = logging.getLogger("blackjack")
    if logger.level == 0: # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(filename='data/blackjack/blackjack.log', encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_listener(check_messages, "on_message")
    bj_manager = Blackjack(bot)
    bot.add_cog(bj_manager)




"""The below module contains code from
Think Python by Allen B. Downey
http://thinkpython.com

Copyright 2012 Allen B. Downey
License: GNU GPLv3 http://www.gnu.org/licenses/gpl.html

Modified heavily for blackjack specific purposes
by Omnifarius

"""

class Card(object):
    """Represents a standard playing card.
    
    Attributes:
      suit: integer 0-3
      rank: integer 1-13
    """

    suit_names = [":clubs:", ":diamonds:", ":hearts:", ":spades:"]
    rank_names = [None, ":a:", ":2:", ":3:", ":4:", ":5:", ":6:", ":7:", ":8:", ":9:", ":10:", ":10:", ":10:", ":10:"]

    def __init__(self, suit=0, rank=2):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        """Returns a human-readable string representation."""
        return '%s %s' % (Card.rank_names[self.rank], Card.suit_names[self.suit])

    def __cmp__(self, other):
        """Compares this card to other, first by suit, then rank.

        Returns a positive number if this > other; negative if other > this;
        and 0 if they are equivalent.
        """
        t1 = self.suit, self.rank
        t2 = other.suit, other.rank
        return cmp(t1, t2)


class Deck(object):
    """Represents a deck of cards.

    Attributes:
      cards: list of Card objects.
    """
    
    def __init__(self):
        self.cards = []
        for suit in range(4):
            for rank in range(1, 14):
                card = Card(suit, rank)
                self.cards.append(card)

    def __str__(self):
        res = []
        for card in self.cards:
            res.append(str(card))
        return ' '.join(res)

    def add_card(self, card):
        """Adds a card to the deck."""
        self.cards.append(card)

    def remove_card(self, card):
        """Removes a card from the deck."""
        self.cards.remove(card)

    def pop_card(self, i=-1):
        """Removes and returns a card from the deck.

        i: index of the card to pop; by default, pops the last card.
        """
        return self.cards.pop(i)

    def shuffle(self):
        """Shuffles the cards in this deck."""
        random.shuffle(self.cards)

    def sort(self):
        """Sorts the cards in ascending order."""
        self.cards.sort()

    def move_cards(self, hand, num):
        """Moves the given number of cards from the deck into the Hand.

        hand: destination Hand object
        num: integer number of cards to move
        """
        for i in range(num):
            hand.add_card(self.pop_card())


class Hand(Deck):
    """Represents a hand of playing cards."""
    
    def __init__(self, owner='', isDealer=False):
        self.cards = []
        self.owner = owner
        self.isDealer = isDealer        
        self.bjhighval = 0
        self.bjlowval = 0
        self.hasAce = False
        self.isBlackjack = False

    def __str__(self):
        output = ''
        if self.isDealer: hideFirst = True
        else: hideFirst = False
        showing_val = 0
        for card in self.cards:
            if hideFirst:
                output += ":question: :question: "
                hideFirst = False
            else:
                if card.rank > 10: showing_val += 10
                else: showing_val += card.rank
                output += card.rank_names[card.rank] + " " + card.suit_names[card.suit] + " "
        value_str = str(showing_val)
        total_str = " Total: "
        if self.isDealer:
            total_str = " Showing: "
            if showing_val == 1:
                value_str = "1/11"
        else:
            if self.hasAce and self.bjlowval <= 11:
                value_str = str(self.bjlowval) + "/" + str(self.bjhighval)
        output = self.owner + "'s hand: " + output + total_str + value_str
        return output

    def add_card(self, card):
        """Adds a card to the hand.  
           Updates low and high blackjack values.
           Updates Hand self.xxx info"""
        self.cards.append(card)
        if card.rank > 10:
            self.bjlowval += 10
        else:
            self.bjlowval += card.rank
            if card.rank == 1:
                self.hasAce = True
        if self.hasAce:
            if (self.bjlowval + 10) <= 21:
                self.bjhighval = self.bjlowval + 10
            else:
                self.bjhighval = self.bjlowval
        else:
            self.bjhighval = self.bjlowval
        if self.bjhighval == 21 and len(self.cards) == 2:
            self.isBlackjack = True


def find_defining_class(obj, method_name):
    """Finds and returns the class object that will provide 
    the definition of method_name (as a string) if it is
    invoked on obj.

    obj: any python object
    method_name: string method name
    """
    for ty in type(obj).mro():
        if method_name in ty.__dict__:
            return ty
    return None

