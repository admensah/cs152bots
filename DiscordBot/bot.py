# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report, State
from reg import Regex, Regex_state
import pdb
import heapq
import openai

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']


class Moderator:
    HELP_KEYWORD = "help"
    PEEK_KEYWORD = "peek"
    REVIEW_KEYWORD = "review"
    COUNT_KEYWORD = "count"
    REGEX_KEYWORD = "regex"
    SEVERITY_LEVELS = 4

class ModBot(discord.Client):

    NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # required to perceive user reactions in DMs for some weird reason. i spent so long on this. RIP.
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.filed_reports = {} # Map from user IDs to the state of their filed report
        self.reports_to_review = [] # Priority queue of (user IDs, index)  state of their filed report
        self.report_counter = 0 # Count of filed reports
        self.reports_in_review = {} # Map from bot_message id to report
        self.false_reporters = [] # List of reporters 
        self.pattern_list = {
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b': "Doxxing", 
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b': "Doxxing",
            r'\b(?:kill|hurt|threat|attack|destroy)\b': "Imminent Danger",
            r'hate': "Hate speech",
            }
        self.regex_op = {}
        self.severity = {
            "Doxxing": 3,
            "Imminent Danger": 4,
            "Extortion": 3,
            "Cyberstalking": 2,
            "Threats": 2, 
            "Swatting": 3,
            "Profanity": 2,
            "Hate speech": 2,
            "Spam": 2,
            "Offesnive Content": 2,
        }

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def on_reaction_add(self, reaction, user):
        '''
        This function is called whenever a reaction is added in a channel that the bot can see.
        '''
        # Ignore reactions from the bot
        if user.id == self.user.id:
            return

        if reaction.message.guild: # Moderator flow
            if reaction.message.id in self.reports_in_review:
                report = self.reports_in_review[reaction.message.id]
                await report.handle_reaction(reaction, self.false_reporters)


        elif user.id in self.reports: # User flow
            report = self.reports[user.id]
            if reaction.message == report.message:
                await self.reports[user.id].handle_reaction(reaction, self.false_reporters)
                
                bot_id = self.user.id
                fake_message = reaction.message
                fake_message.author.id = user.id

                await self.handle_dm(fake_message)
                self.user.id = bot_id
        

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            bot_message = await message.channel.send(r)
        
        self.reports[author_id].message = bot_message

        # handle reactions
        if self.reports[author_id].reaction_mode:
            
            if (self.reports[author_id].state == State.AWAITING_REASON):
                for _ in range(len(self.reports[author_id].REASONS)):
                    await bot_message.add_reaction(self.NUMBERS[_])
            elif (self.reports[author_id].state == State.AWAITING_SUBREASON):
                for _ in range(len(self.reports[author_id].SUB_REASONS[self.reports[author_id].reason])):
                    await bot_message.add_reaction(self.NUMBERS[_])
            elif (self.reports[author_id].state == State.ADDING_CONTEXT or 
                    self.reports[author_id].state == State.ADDING_MESSAGES or 
                    self.reports[author_id].state == State.CHOOSE_BLOCK):
                await bot_message.add_reaction("✅")
                await bot_message.add_reaction("❌")

        # If the report is filed, save it, cache it in a priority queue, and alert #mod channel for review.
        if self.reports[author_id].report_filed():
            if author_id in self.filed_reports:
                self.filed_reports[author_id].append(self.reports[author_id])
            else:
                self.filed_reports[author_id] = [self.reports[author_id]]
            
            # Add to priority queue
            priority = self.reports[author_id].priority()
            index = len(self.filed_reports[author_id]) - 1
            heapq.heappush(self.reports_to_review, (priority, self.report_counter, (author_id, index)))
            self.report_counter += 1

             # Send a message in the mod channel
            for guild in self.guilds:
                for channel in guild.text_channels:
                    if channel.name == f'group-{self.group_num}-mod':
                        mod_channel = channel
            report_summary = self.reports[author_id].summary()
            reply = "---\n"
            reply += f"New report added to the queue:\n{report_summary}"
            reply +=  "Use the `peek` command to look at the most urgent report.\n"
            reply += "Use the `count` command to see how many reports are in the review queue.\n"
            reply += "Use the `review` command to review the most urgent report.\n"
            await mod_channel.send(reply)
        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def auto_flag_messages(self, message, offense):
        if offense in self.severity and self.severity[offense] >= 10:
            await message.delete()
        return
    
    async def auto_report(self, message, offense):
        self.reports["Bot"] = Report(self, [offense, offense, message])
        priority = self.reports["Bot"].priority()
        if "Bot" in self.filed_reports:
            self.filed_reports["Bot"].append(self.reports["Bot"])
        else:
            self.filed_reports["Bot"] = [self.reports["Bot"]]
        index = len(self.filed_reports["Bot"]) - 1
        heapq.heappush(self.reports_to_review, (priority, self.report_counter, ("Bot", index)))
        self.report_counter += 1
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    mod_channel = channel
        report_summary = self.reports["Bot"].summary()
        reply = "---\n"
        reply += f"New report added to the queue:\n{report_summary}"
        reply +=  "Use the `peek` command to look at the most urgent report.\n"
        reply += "Use the `count` command to see how many reports are in the review queue.\n"
        reply += "Use the `review` command to review the most urgent report.\n"
        await mod_channel.send(reply)
        return 
    
    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" or "group-#-mod" channel
        if message.channel.name == f'group-{self.group_num}':
            # Forward the message to the mod channel
            mod_channel = self.mod_channels[message.guild.id]
            await mod_channel.send(f'---\nForwarded message:\n{message.author.name}: "{message.content}"')
            scores = self.eval_text(message.content)
            await mod_channel.send(self.code_format(scores))
            await self.auto_report(message, scores[1])
            await self.auto_flag_messages(message, scores[1])
            return 

        # Moderator flow
        if message.channel.name == f'group-{self.group_num}-mod':
            if message.content == Moderator.HELP_KEYWORD:
                reply =  "Use the `peek` command to look at the most urgent report.\n"
                reply += "Use the `count` command to see how many reports are in the review queue.\n"
                reply += "Use the `review` command to review the most urgent report.\n"
                reply += "Use the `regex` commend to view and edit the regex matching list\n"
                await message.channel.send(reply)
                return

            if message.content == Moderator.COUNT_KEYWORD:
                reply = f"There are currently {len(self.reports_to_review)} reports to review.\n"
                await message.channel.send(reply)
                return

            if message.content == Moderator.PEEK_KEYWORD:
                if len(self.reports_to_review) == 0:
                    reply = "No reports to review!"
                else:
                    reply = f"1 of {len(self.reports_to_review)} reports:\n"
                    _, _, info = self.reports_to_review[0]
                    author_id, index = info
                    report = self.filed_reports[author_id][index]
                    reply += report.summary()
                await message.channel.send(reply)
                return

            if message.content == Moderator.REVIEW_KEYWORD:
                if len(self.reports_to_review) == 0:
                    reply = "No reports to review!"
                    await message.channel.send(reply)
                    return

                # Review top item
                reply = f"1 of {len(self.reports_to_review)} reports:\n"
                _, _, info = self.reports_to_review.pop(0)
                author_id, index = info
                report = self.filed_reports[author_id][index]
                reply += report.summary()
                await message.channel.send(reply)

                report.state = State.AWAITING_REVIEW

                responses = await report.handle_message(message)
                for r in responses:
                    bot_message = await message.channel.send(r)
                
                report.message = bot_message

                # handle reactions
                for _ in range(Moderator.SEVERITY_LEVELS):
                    await bot_message.add_reaction(self.NUMBERS[_])

                self.reports_in_review[report.message.id] = report
                return

            author_id = message.author.id

            if message.content == Moderator.REGEX_KEYWORD:
                self.regex_op[author_id] = Regex(self, self.pattern_list)
            
            if author_id in self.regex_op:
                if self.regex_op[author_id].regex_complete():
                    self.regex_op.pop(author_id)
                    return
                response = await self.regex_op[author_id].handle_message(message)
                await message.channel.send(response)


    def match_regex(self, message):
        for key in self.pattern_list:
            regex = re.compile(key)
            if regex.search(message) != None:
                return self.pattern_list[key]
        return None
    
    def eval_text(self, message):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        matched_regex = self.match_regex(message)

        if matched_regex != None:
            return [message, matched_regex]

        conversation = [
        {"role": "system", "content": "You are a content moderation system. Classify each input as either Doxxing, Extortion, Threats, Sexual Harassment, Hate Speech, Bullying, or . Then assign a severity level to it between 1 and 4, 4 being the most severe. The message you return should be in the format 'Type (Severity)' unless its Doxxing then return 'Doxxing (Type of Doxxing)' or 'clean' if it is a normal message"},
        {"role": "user", "content": message}
        ]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation,
            max_tokens=10  # Adjust the max tokens based on the desired response length
        )
        # TODO: conversation should be kept track of so GPT-4 has more context and can make better decisions
        # TODO: either here or somewhere else, if its doxxing or something very severe we might want to remove the post
        # otherwise we would just send it to the mod channel with the description
        return [message, response.choices[0].message.content]

    
    def code_format(self, list):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Evaluated: '" + list[0]+ "' as " + list[1]


client = ModBot()
client.run(discord_token)