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
import re

class Blackjack:
    """Blackjack

    A module for betting against the house!"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = fileIO("data/blackjack/settings.json", "load") 
        self.bj_sessions = []
        self.payday_register = {}
        economy_cog = self.bot.get_cog("Economy")
        if economy_cog is None:
            print("Sorry, but blackjack relies on the economy cog.  Please ensure economy is loaded before loading blackjack.")
        else:
            self.bank = economy_cog.bank

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
        if seconds < 5:
            await self.bot.say("Bet timeout interval must be more than 5")
            return
        self.settings["BET_TIMEOUT"] = seconds
        await self.bot.say("Blackjack bet timeout is now: " + str(self.settings["BET_TIMEOUT"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)

    @blackjackset.command(name="delay", pass_context=True)
    async def delay(self, ctx, seconds : int):
        """Seconds until user times out.
        """
        if seconds < 10:
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

    @blackjackset.command(name="decks", pass_context=True)
    async def decks(self, ctx, decks : int):
        """Number of decks in the shoe.
        """
        if decks < 1 or decks > 8:
            await self.bot.say("Number of decks must be between 1 and 8 inclusive")
            return
        self.settings["DECKS"] = decks
        await self.bot.say("Number of decks is now: " + str(self.settings["DECKS"]))
        fileIO("data/blackjack/settings.json", "save", self.settings)

    @commands.group(name="blackjack", pass_context=True)
    async def _blackjack(self, ctx):
        """Play Blackjack!!

        Step 1:  '!bank register' to open a blackjack account.
        Step 2:  '!payday' will get you some credits!
        Step 3:  '!sit' to start a game (or join an existing one).  
            3a:   Pick a seat [1-6] when you '!sit' or the dealer will pick for you.
        Step 4:   Place a 'bet' at the table and follow dealer instructions from there.  
        Step 5:  '!getup' when you're finished playing, or just let yourself time out.
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

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
    @checks.mod_or_permissions(manage_server=True)
    async def sessions(self):
        """Displays the number of sessions"""
        sessions = len(self.bj_sessions)
        await self.bot.say("Sessions: "+str(sessions))
        channels = []
        for sess in self.bj_sessions:
            channels.append(str(sess.channel))

    @commands.command(pass_context=True, no_pm=True)
    async def sit(self, ctx, seat : int=1):
        """Starts or joins the blackjack table!
           Optional, pick a position [1-6] (if it's open).
        """
        doneSeating = False
        message = ctx.message
        author = message.author
        if not self.bank.account_exists(author):
            await self.bot.say("{}, you need an account to play blackjack. Type {}bank register to open one.".format(author.mention, ctx.prefix))
            return

        if await get_bj_by_channel(message.channel):
            session = await get_bj_by_channel(message.channel)
        else:
            session = BlackjackSession(message, self.settings)
            self.bj_sessions.append(session)
        
        players = session.bjtable.values()
        #probably need a SEAT LOCK at some point ... 
        if seat < 1 or seat > 6:
            await self.bot.say("Sorry, but please pick a seat between 1 and 6.")
        elif author in players:
           await self.bot.say("This isn't musical chairs! Why don't you stay where you are?!")
           #perhaps you'd like to move seats?  program that later
        else:
            if seat not in session.bjtable.keys():
                session.bjtable[seat] = author
                await self.bot.say("Seated player {0} at position {1}.".format(author.name, str(seat)))
                doneSeating = True
            else:
                newseat = 1
                while newseat <= 6 and not doneSeating:
                    if newseat not in session.bjtable.keys():
                        session.bjtable[newseat] = author
                        doneSeating = True
                        await self.bot.say("Seated player {0} at position {1}.".format(author.name, str(newseat)))
                    newseat += 1
            if not doneSeating:
                await self.bot.say("Sorry, no more seats available!  Wait until one opens up!")
        if not session.active and doneSeating: await session.dealer_waiting()

    @commands.command(pass_context=True, no_pm=True)
    async def getup(self, ctx):
        """Get up from the blackjack table
        """
        message = ctx.message
        author = message.author
        if await get_bj_by_channel(message.channel):
            session = await get_bj_by_channel(message.channel)
            if author in session.bjtable.values():
                for seat in session.bjtable:
                    if session.bjtable[seat] == author:
                        removeseat = seat
                await self.bot.say("Thanks for playing.  Come back again soon, {}".format(author.name))
                tempplayer = session.bjtable.pop(removeseat)
                if len(session.bjtable) == 0:  session.stop = True
            else: 
                await self.bot.say("Sorry, {}, but you're not sitting at a table.".format(author.name))
        else:
            await self.bot.say("Sorry, but there's no blackjack table started, let alone one to stand up from.  Why don't you !sit down and start one.")


class BlackjackSession():
    def __init__(self, message, settings):
        self.channel = message.channel
        self.settings = settings
        self.commands = ["hit", "stand", "stay", "double", "split", "surrender"]
        self.stop = False
        self.dealerReady = True
        self.betReady = False
        self.status = "awaiting bets"
        self.timer = None
        self.bettimer = None
        self.count = 0 #hands played
        self.pbjcount = 0 #player blackjacks
        self.dbjcount = 0 #dealer blackjacks
        self.bets = {} #[player]bet
        self.lastbets = {} #[player]bet
        self.startbal = {} #[player]balance
        self.hands = {} #[player][[Hands]]
        self.blackjacks = [] #[user]
        self.shoe = Shoe() #shoe of 1 Decks()
        self.active = False
        self.activeUser = None
        self.bjtable = {} #[seat1-6]player
        self.dealerhand = None 
        self.splitcount = 0

    async def check_command(self, message):
        foundcom = False
        if message.author in self.bjtable.values():
            if "bet" in message.content.lower():
                await self.do_bet(message)
            #if "bug" in message.content.lower():
            #    print("**** Someone mentioned a BUG *****")
        if message.author == self.activeUser:
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
        #add a "confused" status if more than one command present?

    async def do_bet(self, message):
        """Establish a bet on the table"""
        author = message.author
        channel = message.channel
        
        match = re.search(r'bet\D?(\d+)', message.content.lower())
        if match: 
            bet = int(match.group(1))
        else: 
            if message.content.lower() == "bet" and author in self.lastbets.keys():
                    bet = self.lastbets[author]  #repeat previous
            else:
                return
        
        if not bj_manager.bank.account_exists(author):
            await bj_manager.bot.send_message(channel, "{} You need an account to play blackjack. Type {}bank register to open one.".format(author.mention, ctx.prefix))
            return
        if bj_manager.bank.can_spend(author, bet):
            if bet >= self.settings["MIN_BET"] and bet <= self.settings["MAX_BET"]:
                if self.status == "awaiting bets" or self.status == "active bets":  
                    self.status = "active bets"
                    await bj_manager.bot.send_message(channel, "Bet {2} accepted, dealing soon.  {0}'s balance is: {1}".format(author.name, str(bj_manager.bank.get_balance(author)), str(bet)))
                    self.bets[author] = bet
                    self.betReady = True
                    if author not in self.startbal:
                        self.startbal[author] = bj_manager.bank.get_balance(author)
                else:
                    await bj_manager.bot.send_message(channel, "Sorry, {}, but please wait until I'm accepting bets!".format(author.mention))
            else:
                await bj_manager.bot.send_message(channel, "{0} Bid must be between {1} and {2}.".format(author.mention, self.settings["MIN_BET"], self.settings["MAX_BET"]))
        else:
            await bj_manager.bot.send_message(channel, "{0} You need an account with enough funds to play the blackjack table.".format(author.mention))

    async def dealer_waiting(self):
        """Bulk of the while loop for the dealer wait period"""
        self.active = True
        self.status = "awaiting bets"
        self.timer = int(time.perf_counter())        
        await bj_manager.bot.change_status(discord.Game(name="Blackjack"))
        while not self.stop and abs(self.timer - int(time.perf_counter())) <= self.settings["ACTIVE_TIMEOUT"]:
            if self.dealerReady: await bj_manager.bot.say("Dealer Ready!  Place your bets now please.")
            self.dealerReady = False
            await asyncio.sleep(1)
            if self.status == "active bets":
                self.status == "dealing"
                self.bettimer = int(time.perf_counter())
                self.betReady = True
                while abs(self.bettimer - int(time.perf_counter())) <= self.settings["BET_TIMEOUT"]:
                    if self.betReady: 
                        endtime = self.settings["BET_TIMEOUT"] - abs(self.bettimer - int(time.perf_counter()))
                        await bj_manager.bot.say("Betting ends in {} seconds".format(str(endtime)))
                        self.betReady = False
                    await asyncio.sleep(1)
                await self.init_deal()
            elif self.stop:
                await self.stop_bj()
        if not self.stop:
            await bj_manager.bot.say("Sorry, you took too long to bet!  Closing table.")
            await self.stop_bj()
        
    async def active_dealer(self, splitindex):
        """Bulk of the while loop for the active dealer loop"""
        self.timer = int(time.perf_counter()) #reset timer
        if self.hands[self.activeUser][splitindex].isBlackjack:
            self.hands[self.activeUser][splitindex].bet *= 2
            await bj_manager.bot.say("BLACKJACK!  Congrats, {}.".format(self.activeUser.mention))  
            self.pbjcount += 1
            self.blackjacks.append(self.activeUser)
            self.timer -= self.settings["ACTIVE_DELAY"] #unnecessary
            self.status = "blackjack"
        else:
            await bj_manager.bot.say("{}, you're up!  What action would you like to perform now?".format(self.activeUser.mention))
            while not self.stop and abs(self.timer - int(time.perf_counter())) <= self.settings["ACTIVE_DELAY"]:
                if abs(self.timer - int(time.perf_counter())) == self.settings["ACTIVE_DELAY"]:
                    await bj_manager.bot.say("{} timed out.".format(self.activeUser.name))
                    self.status = "standing"
                if self.status == "hitting":
                    await self.do_hit(splitindex)
                elif self.status == "standing":
                    await bj_manager.bot.say("{} stands.".format(self.activeUser.name))
                    self.timer -= self.settings["ACTIVE_DELAY"]
                    self.status = "dealing"
                elif self.status == "doubling":
                    if len(self.hands[self.activeUser][splitindex]) == 2:
                        if bj_manager.bank.can_spend(self.activeUser, self.bets[self.activeUser]*2):
                            self.hands[self.activeUser][splitindex].bet *= 2
                            await self.do_hit(splitindex)
                            self.timer -= self.settings["ACTIVE_DELAY"]
                        else: 
                            await bj_manager.bot.say("Not enough funds, you can just hit instead")
                    else:
                        await bj_manager.bot.say("Sorry, but you can only double down on your initial two card hand.  Try hitting.")
                    self.status = "dealing"
                elif self.status == "splitting":
                    if self.hands[self.activeUser][splitindex].isSplittable():
                        if bj_manager.bank.can_spend(self.activeUser, self.hands[self.activeUser][splitindex].bet*2):
                            await self.do_split(splitindex)
                            return #escape this active_deal, do_split calls two new ones!
                        else:
                            await bj_manager.bot.say("Not enough funds, you can just hit/stay instead")
                    else:
                        await bj_manager.bot.say("Sorry, but that is not a splittable hand!")
                    self.status = "dealing"
                elif self.status == "surrendering":
                    if len(self.hands[self.activeUser][splitindex]) == 2:
                        await bj_manager.bot.say("{} surrenders and gets half their bet back.".format(self.activeUser.name))
                        self.hands[self.activeUser][splitindex] *= -0.5
                        self.timer -= self.settings["ACTIVE_DELAY"]
                    else:
                        await bj_manager.bot.say("Sorry, but you can only surrender your initial hand.")
                    self.status = "dealing"
                await asyncio.sleep(1)
        self.status = "dealing"
        
    async def do_hit(self, splitindex):
        """Hit function for players"""
        self.shoe.move_cards(self.hands[self.activeUser][splitindex], 1)
        await bj_manager.bot.say(self.hands[self.activeUser][splitindex])
        self.timer = int(time.perf_counter())
        self.status = "dealing"
        if self.hands[self.activeUser][splitindex].bjhighval > 21:
            await bj_manager.bot.say("{0} busted with {1}".format(self.activeUser.name, str(self.hands[self.activeUser][splitindex].bjhighval)))
            self.hands[self.activeUser][splitindex].bet *= -1
            self.timer -= self.settings["ACTIVE_DELAY"]
        elif self.hands[self.activeUser][splitindex].bjhighval == 21:
            self.status = "standing"

    async def do_split(self, splitindex):
        """Split function for players"""
        self.splitcount += 1
        self.status = "dealing"
        h1 = Hand(self.activeUser, False, self.hands[self.activeUser][splitindex].bet)
        h2 = Hand(self.activeUser, False, self.hands[self.activeUser][splitindex].bet)
        self.hands[self.activeUser][splitindex].move_cards(h1, 1)
        self.hands[self.activeUser][splitindex].move_cards(h2, 1)
        self.shoe.move_cards(h1, 1)
        self.shoe.move_cards(h2, 1)
        self.hands[self.activeUser][splitindex] = h1
        self.hands[self.activeUser].append(h2)
        await bj_manager.bot.say(self.dealerhand)
        await bj_manager.bot.say(self.hands[self.activeUser][self.splitcount])
        await self.active_dealer(self.splitcount)
        await bj_manager.bot.say(self.dealerhand)
        await bj_manager.bot.say(self.hands[self.activeUser][splitindex])
        await self.active_dealer(splitindex)

    async def finish_deal(self):
        """Finalize the dealer's hand actions"""
        self.status = "finishing"
        await bj_manager.bot.say("Revealing Dealer's hand:")
        self.dealerhand.isDealer = False
        await bj_manager.bot.say(self.dealerhand)
        activehands = 0
        for player in self.hands:
            for hand in self.hands[player]:
                if hand.bet > 0:
                    activehands += 1
        activehands -= len(self.blackjacks)
        if activehands >= 1:
            suspensetimer = int(time.perf_counter())
            while self.dealerhand.bjhighval < 21 and abs(suspensetimer - int(time.perf_counter())) <= 20:
                await asyncio.sleep(2) #Waiting for suspense!
                if self.dealerhand.bjhighval >= 17 and self.dealerhand.bjhighval <= 21:
                    await bj_manager.bot.say("Dealer stands at " + str(self.dealerhand.bjhighval))
                    suspensetimer -= 20
                if self.dealerhand.bjhighval < 17:
                    await bj_manager.bot.say("Dealer hits.")
                    self.shoe.move_cards(self.dealerhand, 1)
                    await bj_manager.bot.say(self.dealerhand)
            if self.dealerhand.bjhighval > 21:
                await bj_manager.bot.say("Dealer busts with " + str(self.dealerhand.bjhighval) + ".  Everyone's a winner!  Unless you busted already, sucker.")
            else:
                for player in self.hands: #check who won!
                    for hand in self.hands[player]:  
                        if hand.bet > 0:
                            if self.dealerhand.bjhighval > hand.bjhighval:
                                await bj_manager.bot.say("Sorry, {0}, but you lost with {1}!".format(player.mention, str(hand.bjhighval)))
                                hand.bet *= -1
                            if hand.bjhighval > self.dealerhand.bjhighval:
                                await bj_manager.bot.say("Congrats, {0}, you win with {1}!".format(player.mention, str(hand.bjhighval)))
                            if self.dealerhand.bjhighval == hand.bjhighval:
                                await bj_manager.bot.say("Push at {1}, take back your bet, {0}".format(player.mention, str(hand.bjhighval)))
                                hand.bet = 0
        else:
            if len(self.blackjacks) == 0:
                await bj_manager.bot.say("Sorry table, looks like the house won this round!")
            else:
                await bj_manager.bot.say("Nice blackjack(s)!")
        
        await self.analyze_bets()

    async def reset_dealer(self):
        """Reset globals and start fresh!"""
        self.count += 1 #hands played per session
        self.activeUser = None
        self.hands = {}
        for player in self.bets:
            self.lastbets[player] = self.bets[player]
        self.bets = {}
        self.blackjacks = []
        self.timer = int(time.perf_counter())
        self.bettimer = None
        self.status = "awaiting bets"
        self.dealerReady = True
        self.betReady = False
        if self.stop: await self.stop_bj()

    async def init_deal(self):
        """Deal the table some cards.
        """
        self.shoe = Shoe(self.settings["DECKS"])
        self.shoe.shuffle()
        await bj_manager.bot.say("Shuffling and dealing...")
        for player in self.bets:
            playerhand = Hand(player, False, self.bets[player])
            self.shoe.move_cards(playerhand, 2)
            self.hands[player] = [playerhand]
        self.dealerhand = Hand(bj_manager.bot.user, True, 0)
        self.shoe.move_cards(self.dealerhand, 2)
        await bj_manager.bot.say(self.dealerhand)
        for player in self.hands:
            await bj_manager.bot.say(self.hands[player][0])
        #check for dealer BJ ... offer insurance here eventually?
        if self.dealerhand.isBlackjack:
            self.dbjcount += 1
            await bj_manager.bot.say("Dealer Blackjack!!!")
            self.dealerhand.isDealer = False
            await bj_manager.bot.say(self.dealerhand)
            for player in self.hands:
                if self.hands[player][0].isBlackjack:
                    self.hands[player][0].bet = 0
                    await bj_manager.bot.say("Push for {}".format(player.mention))
                else: 
                    await bj_manager.bot.say("Sorry {}.  You lose".format(player.mention))
                    self.hands[player][0].bet *= -1
            await self.analyze_bets()
        else:
            self.status = "dealing"
            firstPlayer = True
            for player in self.hands.keys():
                if not firstPlayer:
                    await bj_manager.bot.say(self.dealerhand)
                    await bj_manager.bot.say(self.hands[player][0])
                firstPlayer = False
                self.activeUser = player
                self.splitcount = 0
                await self.active_dealer(0)
            self.activeUser = bj_manager.bot.user
            await self.finish_deal()

    async def analyze_bets(self):
        """Finalize bets and adjust the blackjack bank!"""
        for player in self.hands:
            for hand in self.hands[player]: 
                if hand.bet > 0:
                    bj_manager.bank.deposit_credits(player, hand.bet)
                elif hand.bet < 0:
                    bj_manager.bank.withdraw_credits(player, hand.bet * -1)
                await bj_manager.bot.say("{0}, your new balance is: {1}".format(player.mention, str(bj_manager.bank.get_balance(player))))
        await self.reset_dealer()

    async def stop_bj(self):
        biggestwinner = "None"
        biggestloser = "None"
        biggestwinnings = 0
        biggestlosses = 0
        for player in self.startbal:
            balance = bj_manager.bank.get_balance(player)
            diff = balance - self.startbal[player]
            if diff > 0 and diff > biggestwinnings:
                biggestwinner = player.name
                biggestwinnings = diff
            if diff < 0 and diff < biggestlosses:
                biggestloser = player.name
                biggestlosses = diff 
        output = "Blackjack ended.\nSession Stats:\nHands played: " + str(self.count)
        output = output + "\nPlayer blackjacks:" + str(self.pbjcount)
        output = output + "\nDealer blackjacks:" + str(self.dbjcount)
        if biggestwinner != "None":
            output = output + "\nBiggest Winner: " + biggestwinner + " winning " + str(biggestwinnings)
        if biggestloser != "None":
            output = output + "\nBiggest Loser: " + biggestloser + " losing " + str(biggestlosses)
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
        logger.info("Creating data/blackjack folder...")
        os.makedirs("data/blackjack")

def check_files():
    settings = {"ACTIVE_TIMEOUT" : 45, "MIN_BET" : 10, "MAX_BET" : 1000, "DECKS" : 1, "ACTIVE_DELAY" : 20, "BET_TIMEOUT" : 10}

    f = "data/blackjack/settings.json"
    if not fileIO(f, "check"):
        logger.info("Creating default blackjack's settings.json...")
        fileIO(f, "save", settings)
    else: #consistency check
        current = fileIO(f, "load")
        if current.keys() != settings.keys():
            for key in settings.keys():
                if key not in current.keys():
                    current[key] = settings[key]
                    logger.info("Adding " + str(key) + " field to economy settings.json")
            fileIO(f, "save", current)

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

    #suit and rank names specific to Discord emoji sets
    #had to get a little creative with JQK
    suit_names = [":clubs:", ":diamonds:", ":hearts:", ":spades:"]
    rank_names = [None, ":a:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:", ":ten:", ":baby_symbol:", ":womens:", ":mens:"]

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


class Shoe(Deck):
    """Represents a shoe with multiple decks of cards."""

    def __init__(self, deckcount=1):
        self.cards = []
        self.decks = deckcount  #default single deck!
        for _ in range(self.decks):
            for suit in range(4):
                for rank in range(1, 14):
                    card = Card(suit, rank)
                    self.cards.append(card)

    def __len__(self):
        return len(self.cards)

class Hand(Deck):
    """Represents a hand of playing cards."""
    
    def __init__(self, owner=None, isDealer=False, bet=0):
        self.cards = []
        self.owner = owner
        self.isDealer = isDealer
        self.bet = bet
        self.bjhighval = 0
        self.bjlowval = 0
        self.hasAce = False
        self.isBlackjack = False

    def __len__(self):
        return len(self.cards)

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
            if self.bjhighval == 21:
                value_str = "21 !!"
            elif self.hasAce and self.bjlowval <= 11:
                value_str = str(self.bjlowval) + "/" + str(self.bjhighval)
        output = self.owner.name + "'s hand: " + output + total_str + value_str
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

    def isSplittable(self):
        """Returns True if hand can be split
           Two card hands only
           Rank must be equal"""
        if len(self.cards) != 2:  
            return False
        else:
            if self.cards[0].rank == self.cards[1].rank:  return True
            elif self.cards[0].rank >= 10 and self.cards[1].rank >= 10: return True
        return False


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

