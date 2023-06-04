from enum import Enum, auto
import discord 
import re

class Regex_state(Enum):
    REGEX_MODE = auto()
    REGEX_WAIT = auto()
    REGEX_ADD = auto()
    REGEX_ADDED = auto()
    REGEX_REMOVE = auto()
    REGEX_DELETED = auto()
    REGEX_CANCELLED = auto()
    REGEX_DONE = auto()
    

class Regex:
    ADD_REGEX_KEYWORD = "add"
    REMOVE_REGEX_KEYWORD = "remove"
    VIEW_REGEX_KEYWORD = "view"
    CANCEL_REGEX_KEYWORD = "cancel"

    def __init__(self, client, pattern_list):
        self.state = Regex_state.REGEX_MODE
        self.client = client
        self.mod = None
        self.regex_list = pattern_list
        self.key = None

    async def handle_message(self, message):
        if message.content == self.CANCEL_REGEX_KEYWORD:
            self.state = Regex_state.REGEX_CANCELLED
            return "Cancelled"

        if self.state == Regex_state.REGEX_MODE:
            reply = "Welcome to regex mode\n"
            reply += "Type `add` to add a new filter pattern\n"
            reply += "Type `remove` to remove a filter pattern\n"
            reply += "Type `view` to view all the filter patterns\n"
            reply += "You can type `cancel` at anytime to get out of this mode\n"
            self.state = Regex_state.REGEX_WAIT
            self.mod = message.author
            return reply

        if self.state == Regex_state.REGEX_WAIT:
            if message.content == self.ADD_REGEX_KEYWORD:
                reply = "Please type the regex pattern you would like to filter out\n"
                self.state = Regex_state.REGEX_ADD
                return reply 
            elif message.content == self.REMOVE_REGEX_KEYWORD:
                reply = "These are the current filter patterns\n"
                for key in self.regex_list:
                    reply += f"```[{key}] regex is for: {self.regex_list[key]}```"
                reply += "Please type in the regex (Without the sqaure brackets) you want removed"
                self.state = Regex_state.REGEX_REMOVE
                return reply
            elif message.content == self.VIEW_REGEX_KEYWORD:
                reply = "These are the current filter patterns\n"
                for key in self.regex_list:
                    reply += f"```[{key}] regex is for: {self.regex_list[key]}```"
                self.state = Regex_state.REGEX_DONE
                return reply
            
        if self.state == Regex_state.REGEX_ADD:
            try:
                re.compile(message.content)
                self.key = message.content
                reply = "Please specify what type of abuse this regex filters out\n"
                self.state = Regex_state.REGEX_ADDED
                return reply
            except:
                reply = "Sorry the regex " + message.content + " is not formatted correctly\n"
                return reply
        
        if self.state == Regex_state.REGEX_ADDED:
            reply = "Messages that match the regex `" + self.key + "` are now filtered out because of `" + message.content + "`\n"
            self.state = Regex_state.REGEX_DONE
            self.regex_list[self.key] = message.content
            return reply

        if self.state == Regex_state.REGEX_REMOVE:
            try: 
                re.compile(message.content)
                self.regex_list.pop(message.content)
                self.state = Regex_state.REGEX_DELETED
                reply = "The Regex `" + message.content + "` is now removed from the filter list\n"
                return reply
            except:
                reply = "Sorry the regex `" + message.content + "` doesn't match any of the filtered regexes\n"
                self.state = Regex_state.REGEX_DONE
                return reply 
        
        return


    def regex_complete(self):
        return self.state in [Regex_state.REGEX_CANCELLED, Regex_state.REGEX_DONE]

