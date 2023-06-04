from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    AWAITING_REASON = auto()
    AWAITING_SUBREASON = auto()
    ADDING_CONTEXT = auto()
    ADDING_MESSAGES = auto()
    AWAITING_CONTEXT = auto()
    CHOOSE_BLOCK = auto()
    REPORT_CANCELED = auto()
    REPORT_FILED = auto()
    AWAITING_REVIEW = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    REASONS = ["Harassment", "Offensive Content", "Spam", "Imminent Danger"]
    NON_FOCUS_REASONS = ["Offensive Content", "Spam", "Imminent Danger"]
    SUB_REASONS = {
        "Harassment": ["Doxxing", "Cyberstalking", "Threats", "Hate Speech", "Sexual Harassment", "Bullying", "Extortion", "Other"],
        "Offensive Content": ["Child Sexual Abuse Material", "Adult Sexually Explicit Content", "Violence", "Hate Speech", "Copyright Infringement"],
        "Spam": ["Impersonation", "Solicitation", "Malware"],
        "Imminent Danger": ["Violence to Others", "Self-Harm"]
    }
    HELP_KEYWORD = "help"
    NUM_TO_IND = {
        "1️⃣": 1, 
        "2️⃣": 2, 
        "3️⃣": 3, 
        "4️⃣": 4, 
        "5️⃣": 5, 
        "6️⃣": 6, 
        "7️⃣": 7, 
        "8️⃣": 8, 
        "9️⃣": 9
    }

    NO_CONTEXT = "No additional context"
    
    EMOJI_YN = {
        "✅": True,
        "❌": False
    }

    def __init__(self, client, args=None):
        if args != None:
            self.state = State.REPORT_FILED
            self.client = client
            self.reason = args[0]
            self.sub_reason = args[1]
            self.additional_messages = False
            self.additional_context = True
            self.choose_block = False
            self.reaction_mode = False
            self.flagged_messages = [args[2]]
            self.user_context = "Bot detected"
            self.severity = None
            self.reporter = "Bot"
            return

        self.state = State.REPORT_START
        self.client = client
        self.message = None # keeps track of last sent message (useful for handling reactions)
        self.reason = None
        self.sub_reason = None
        self.additional_messages = False
        self.additional_context = False
        self.choose_block = False
        self.reaction_mode = False
        self.flagged_messages = []
        self.user_context = None # user inputted context
        self.severity = None
        self.reporter = None
    async def handle_message(self, message, user_db):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_CANCELED
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            self.reporter = message.author
            return [reply]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
                if message not in self.flagged_messages: 
                    self.flagged_messages.append(message)
                else:
                    return ["It seems this message has already been added. Please try again or say `cancel` to cancel."]
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
        
        if self.state == State.MESSAGE_IDENTIFIED:
            if self.reason == None:
                self.state = State.AWAITING_REASON
                self.reaction_mode = True
                return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Please select the reason for reporting this message:\n1️⃣: Harassment\n2️⃣: Offensive Content\n3️⃣: Spam\n4️⃣: Imminent Danger"]
            else:
                self.state = State.ADDING_MESSAGES
                message_count = len(self.flagged_messages)
                self.reaction_mode = True
                return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                        f"Would you like to add more relevant chat messages? You have currently submitted {message_count} message(s). Yes or No"]

        if self.state == State.AWAITING_REASON:
            if self.reason == None:
                return ["Please select the reaction corresponding to your valid reason for reporting."]
            else:
                self.reaction_mode = True
                self.state = State.AWAITING_SUBREASON
                if self.reason == "Harassment":
                    return ["Please select the type of Harassment:\n1️⃣: Doxxing\n2️⃣: Cyberstalking\n3️⃣: Threats\n4️⃣: Hate Speech\n5️⃣: Sexual Harassment\n6️⃣: Bullying\n7️⃣: Extortion\n8️⃣: Other"]
                if self.reason == "Offensive Content":
                    return ["Please select the type of Offensive Content:\n1️⃣: Child Sexual Abuse Material\n2️⃣: Adult Sexually Explicit Content\n3️⃣: Violence\n4️⃣: Hate Speech\n5️⃣: Copyright Infringement"]
                if self.reason == "Spam":
                    return ["Please select the type of Spam:\n1️⃣: Impersonation\n2️⃣: Solicitation\n3️⃣: Malware"]
                if self.reason == "Imminent Danger":
                    return ["Please select the type of Danger:\n1️⃣: Violence to Others\n2️⃣: Self-Harm"]

        if self.state == State.AWAITING_SUBREASON:
            if self.sub_reason == None:
                return ["Please select the reaction corresponding to your subreason."]
            else:
                self.reaction_mode = True
                if self.reason in self.NON_FOCUS_REASONS:
                    self.state = State.CHOOSE_BLOCK
                    return ["You selected " + self.sub_reason + ". Thank you for reporting. Our content moderation team will review the report and decide on appropriate action. Would you like to block the offending user(s)? Yes or No"]
                else:
                    self.state = State.ADDING_MESSAGES
                    return ["Would you like to include any relevant chat messages that may help us process your report?"]

        if self.state == State.ADDING_MESSAGES:
            if self.additional_messages:
                self.state = State.AWAITING_MESSAGE
                return ["Please provide the links of the relevant chat messages you want to add."]
            else:
                self.state = State.ADDING_CONTEXT
                self.reaction_mode = True
                return ["Would you like to provide any further context that may help us process your report?"]


        if self.state == State.ADDING_CONTEXT:
            if self.additional_context:
                self.state = State.AWAITING_CONTEXT
                return["Please provide any further context for your report."]
            else:
                self.state = State.CHOOSE_BLOCK
                self.reaction_mode = True
                return ["Thank you for reporting. Our content moderation team will review the report and decide on appropriate action. Would you like to block the offending user(s)? Yes or No"]

        if self.state == State.AWAITING_CONTEXT:
            self.user_context = message.content
            self.state = State.CHOOSE_BLOCK
            self.reaction_mode = True
            return ["Thank you for reporting. Our content moderation team will review the report and decide on appropriate action. Would you like to block the offending user(s)? Yes or No"]
            
        if self.state == State.CHOOSE_BLOCK:
            if self.reaction_mode:
                return ["Thank you for reporting. Our content moderation team will review the report and decide on appropriate action. Would you like to block the offending user(s)? Yes or No"]
            else:
                self.state = State.REPORT_FILED
                reply = f"Your report has been submitted for review.\n  Reason: {self.reason}.\n  Subreason: {self.sub_reason}.\n"
                if self.additional_context:
                    reply += f"  You included the following relevant context: {self.user_context}\n"
                if self.choose_block:
                    authors = self.get_authors()
                    reply += f"  The offending authors of the flagged messages have been blocked:\n{authors}"
                    # Create a set to store unique user IDs
                    unique_user_ids = set()

                    # Update blocking and blocked users counts
                    for message in self.flagged_messages:
                        user_id = message.author.id
                        if user_id not in unique_user_ids:
                            unique_user_ids.add(user_id)
                            user_db.update_one(
                                {"user_id": user_id},
                                {"$inc": {"num_users_blocking": 1}},
                                upsert=True
                            )

                    # Update blocked users count for the reporter
                    reporter_id = self.reporter.id
                    if reporter_id not in unique_user_ids:
                        unique_user_ids.add(reporter_id)
                        user_db.update_one(
                            {"user_id": reporter_id},
                            {"$inc": {"num_blocked_users": 1}},
                            upsert=True
                        )
            return [reply]

        if self.state == State.AWAITING_REVIEW:
            if self.severity == None:
                return ["Please select the corresponding severity level."]
            else:
                self.reaction_mode = True
                return ["You selected " + self.severity + ". Thank you for reviewing."]



    async def handle_reaction(self, reaction, user_db):
        self.reaction_mode = False
        if self.state == State.AWAITING_REASON:
            self.reason = self.REASONS[self.NUM_TO_IND[reaction.emoji] - 1] 
        if self.state == State.AWAITING_SUBREASON:
            self.sub_reason = self.SUB_REASONS[self.reason][self.NUM_TO_IND[reaction.emoji] - 1]
        if self.state == State.ADDING_MESSAGES:
            self.additional_messages = self.EMOJI_YN[reaction.emoji]
        if self.state == State.ADDING_CONTEXT:
            self.additional_context = self.EMOJI_YN[reaction.emoji]
        if self.state == State.CHOOSE_BLOCK:
            self.choose_block = self.EMOJI_YN[reaction.emoji]
        if self.state == State.AWAITING_REVIEW:
            self.severity = self.NUM_TO_IND[reaction.emoji]
            if self.severity == 1:
                offendingUsers = []
                offendingUserNames = []
                for message in self.flagged_messages:
                    offendingUser = message.author
                    if offendingUser not in offendingUsers:
                        offendingUsers.append(offendingUser)
                        offendingUserNames.append(offendingUser.name)
                reply = "No action has been taken against " + " ,".join(offendingUserNames) + "\n\n"
                
                await self.message.channel.send("Is this a false report? (yes/no)")             

                def check(m):
                    return m.content in ['yes', 'no', 'Yes', 'No']
                
                response = await self.client.wait_for('message', check=check, timeout=60.0) 
                
                while not check(response):
                    await self.message.channel.send("Is this a false report? Type (yes/no)")
                    response = await self.client.wait_for('message', check=check, timeout=60.0) 

                if response.content in ['yes', 'Yes']:
                    # Update the false_reports count for the reporter
                    user_db.update_one(
                        {"user_id": self.reporter.id},
                        {"$inc": {"false_reports": 1}},
                        upsert=True
                    )

                    # Retrieve the updated value
                    user_document = user_db.find_one({"user_id": self.reporter.id})
                    false_reports = user_document.get('false_reports', 0)

                    if false_reports > 2:
                        await self.reporter.send("Your account is kicked for 3 or more repeated inaccurate reports.")
                    else:
                        await self.reporter.send(f"Ensure future reports are accurate to avoid further action against your account. This is warning {false_reports} of 2.")
                    
                reply += "Use the `peek` command to look at the most urgent report.\n"
                reply += "Use the `count` command to see how many reports are in the review queue.\n"
                reply += "Use the `review` command to review the most urgent report.\n"
                await self.message.channel.send(reply)
                
            if self.severity == 2:
                # Warn offending user
                offendingUsers = []
                offendingUserNames = []
                for message in self.flagged_messages:
                    offendingUser = message.author
                    if offendingUser not in offendingUsers:
                        offendingUsers.append(offendingUser)
                        offendingUserNames.append(offendingUser.name)
                for user in offendingUsers:
                    await user.send("You have been reported for violating the server rules. Please be respectful and follow the guidelines.")
                    user_db.update_one(
                        {"user_id": user.id},
                        {"$inc": {"num_warnings": 1}},
                        upsert=True
                    )
                reply = "The following users have been warned: " + " ,".join(offendingUserNames) + "\n\n"
                reply +=  "Use the `peek` command to look at the most urgent report.\n"
                reply += "Use the `count` command to see how many reports are in the review queue.\n"
                reply += "Use the `review` command to review the most urgent report.\n"
                await self.message.channel.send(reply)
            if self.severity == 3:
                # Delete message and warn offending user
                offendingUsers = []
                offendingUserNames = []
                for message in self.flagged_messages:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        response = "The message does not exist or has already been deleted.\n"
                        await self.message.channel.send(response)
                    offendingUser = message.author
                    if offendingUser not in offendingUsers:
                        offendingUsers.append(offendingUser)
                        offendingUserNames.append(offendingUser.name)
                for user in offendingUsers:
                    await user.send("You have been reported for violating the server rules. Please be respectful and follow the guidelines.")
                reply = "The following user(s) have been warned: " + " ,".join(offendingUserNames) + "\n\n"
                reply += "The message(s) has been deleted.\n"
                reply +=  "Use the `peek` command to look at the most urgent report.\n"
                reply += "Use the `count` command to see how many reports are in the review queue.\n"
                reply += "Use the `review` command to review the most urgent report.\n"
                await self.message.channel.send(reply)
            if self.severity == 4:
                # Delete message and kick offending user
                offendingUsers = []
                offendingUserNames = []
                for message in self.flagged_messages:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        response = "The message does not exist or has already been deleted.\n"
                        await self.message.channel.send(response)
                    offendingUser = message.author
                    if offendingUser not in offendingUsers:
                        offendingUsers.append(offendingUser)
                        offendingUserNames.append(offendingUser.name)
                for user in offendingUsers:
                    await user.send("You have been kicked for violating the server rules. Please be respectful and follow the guidelines.")
                reply = "The following users have been kicked: " +  " ,".join(offendingUserNames) + "\n"
                reply += "The message(s) has been deleted.\n"
                reply +=  "Use the `peek` command to look at the most urgent report.\n"
                reply += "Use the `count` command to see how many reports are in the review queue.\n"
                reply += "Use the `review` command to review the most urgent report.\n"
                await self.message.channel.send(reply)
        return
     
    def get_authors(self):
        authors = [msg.author.name for msg in self.flagged_messages]
        unique_authors = list(set(authors))
        return "\n".join(unique_authors)

    def report_complete(self):
        return self.state in [State.REPORT_CANCELED, State.REPORT_FILED]


    def report_filed(self):
        return self.state == State.REPORT_FILED
    

    # Lower number == Higher priority
    def priority(self):
        if self.reason == "Imminent Danger" or self.sub_reason in ["Doxxing", "Extortion", "Other", "Cyberstalking", "Threats", "Swatting"]:
            return 1
        return 2


    def summary(self):
        summary = ""
        summary += f"Reason: {self.reason}\n"
        summary += f"Subreason: {self.sub_reason}\n"
        summary += f"Additional Context: {self.user_context if self.additional_context else self.NO_CONTEXT}\n"
        summary += f"\n{len(self.flagged_messages)} flagged messages:\n"
        for i, message in enumerate(self.flagged_messages):
            summary += f"```{message.author.name}: {message.content}```"
        return summary
    
