import os
import textwrap
from enum import Enum
from typing import Dict

# import arxiv
from openai import OpenAI
import tiktoken

import interactions
from interactions import Client, Intents, slash_command, SlashContext, slash_option, OptionType, listen, \
    AutoArchiveDuration, ContextMenuContext, message_context_menu, Embed
from interactions.api.events import MessageCreate

from OpenFunctions.BaseFunction import BaseFunction


# class Role(Enum):
#     SYSTEM = "system"
#     USER = "user"
#     ASSISTANT = "assistant"
#     FUNCTION = "function"


class Conversation:
    def __init__(self, channel_id=None, is_thread=False):
        self.messages = [{"role": "system",
                          "content": "You are a chatty, expressive and informative Discord bot named 'Khôi Vĩ AI'. "
                                     "Be helpful with humor and wit. "}]
        self.channel_id = channel_id
        self.is_thread = is_thread

    def add_message(self, role, content):
        message = {"role": role, "content": content}
        self.messages.append(message)
        return self

    def get_messages(self):
        return self.messages

    def pop_message(self):
        self.messages.pop(1)

    # def set_thread(self, thread):
    #     self.thread = thread

    def get_channel_id(self):
        return self.channel_id

    def is_thread(self):
        return self.is_thread


conversations = {}
guild_defaults: Dict[int, int] = {}


def message_option():
    def wrapper(func):
        return slash_option(
            name="message",
            description="Message to send to Khoi Vi AI",
            opt_type=OptionType.STRING,
            required=True
        )(func)

    return wrapper


@listen()
async def on_ready():
    print(f'Logged on as {bot.user}! Owner: {bot.owner.display_name}.')


@listen()
async def on_message_create(event: MessageCreate):
    ctx = event.message
    message = ctx.content

    if event.message.author.id == bot.user.id or not isinstance(ctx.channel, interactions.TYPE_MESSAGEABLE_CHANNEL):
        return

    convo = None

    if isinstance(ctx.channel, interactions.TYPE_DM_CHANNEL):
        convo = conversations.get(ctx.channel.id)
        if not convo:
            conversations[ctx.channel.id] = Conversation(channel_id=ctx.channel.id, is_thread=False)
            convo = conversations[ctx.channel.id]
    elif isinstance(ctx.channel, interactions.TYPE_THREAD_CHANNEL):
        convo = conversations.get(ctx.channel.id)
        if not convo:
            return

    if convo:
        await ctx.channel.trigger_typing()
        convo.add_message(role="user", content=message)
        response = send_message(convo)
        await ctx.channel.send(content=response)


@slash_command(name="enable", description="Enable the bot in this channel.")
async def enable_function(ctx: SlashContext):
    await ctx.defer()
    # if channel type is not guild channel or messageable channel
    if not (isinstance(ctx.channel, (interactions.TYPE_DM_CHANNEL, interactions.TYPE_GUILD_CHANNEL))
            and isinstance(ctx.channel, interactions.TYPE_MESSAGEABLE_CHANNEL)):
        await ctx.respond("This feature cannot be used in this type of channel.")
        return
    conversations[ctx.channel.id] = Conversation(channel_id=ctx.channel.id, is_thread=False)
    await ctx.send(f"Enabled KVAI in {ctx.channel.mention}.")


@slash_command(name="set_default", description="Make this channel the server default.")
async def set_default_function(ctx: SlashContext):
    await ctx.defer()
    # if channel type is not guild channel or messageable channel
    if not (isinstance(ctx.channel, interactions.TYPE_GUILD_CHANNEL)
            and isinstance(ctx.channel, interactions.TYPE_MESSAGEABLE_CHANNEL)):
        await ctx.respond("This feature cannot be used in this type of channel.")
        return
    guild_defaults[ctx.guild.id] = ctx.channel.id
    await ctx.send(f"Set {ctx.channel.mention} as server default.")


@slash_command(name="chat", description="Chat with Khoi Vi AI.")
@message_option()
async def chat_function(ctx: SlashContext, message: str):
    await ctx.defer()
    convo = conversations.get(ctx.channel.id)
    if not convo:
        return await ctx.send(f"This command cannot be used in this channel. Try {enable_function.mention()}.")
    convo.add_message(role='user', content=message)
    response = send_message(convo)
    r_format = f"{textwrap.indent(message, '> ')}\n - {ctx.author.mention}\n\n{response}"
    await ctx.send(content=r_format)


@slash_command(name="thread", description="Create a separate thread to chat with Khoi Vi AI.")
@message_option()
# @slash_option(name="private", description="Whether the thread should be private", opt_type=OptionType.BOOLEAN)
async def thread_function(ctx: SlashContext, message: str):
    await ctx.defer()
    if not conversations.get(ctx.channel.id):
        await ctx.send(f"This command cannot be used in this channel. Try {enable_function.mention()}.")
    thread = await ctx.channel.create_thread(
        name=(ctx.author.name if ctx.author.nick is None else ctx.author.nick + "'s Convo"),
        auto_archive_duration=AutoArchiveDuration.ONE_DAY,
    )
    convo = Conversation(channel_id=thread.id, is_thread=True)
    conversations[thread.id] = convo
    convo.add_message(role='user', content=message)
    response = send_message(convo)
    conversation_title = send_branched_message(convo, "Title this chat in 5 words.")
    await thread.edit(name=conversation_title)
    r_format = f"{textwrap.indent(message, '> ')}\n - {ctx.author.mention}\n\n{response}"
    await thread.send(r_format)
    await ctx.send(f"Created thread {thread.mention}.")


@slash_command(name="generate", description="Generate an image with Khoi Vi AI.")
@slash_option(name="prompt", description="Prompt for the image", opt_type=OptionType.STRING, required=True)
async def generate_function(ctx: SlashContext, prompt: str):
    await ctx.defer()
    convo = conversations.get(ctx.channel.id)
    if not convo:
        return await ctx.send(f"This command cannot be used in this channel. Try {enable_function.mention()}.")
    url = send_image_prompt(prompt)
    r_format = f"{textwrap.indent(prompt, '> ')}\n - {ctx.author.mention}"
    await ctx.send(content=r_format, embed=Embed(images=[url]))


@message_context_menu(name="Send to KVAI", dm_permission=False)
async def send_to_kvai_function(ctx: ContextMenuContext):
    await ctx.defer()
    message = ctx.target.content
    # guild = utils.get(bot.guilds, id=ctx.guild_id)
    # channel = utils.get(guild.channels, id=guild_defaults[ctx.guild_id])

    convo = Conversation()
    convo.add_message(role='user', content=message)
    response = send_message(convo)
    r_format = f"{textwrap.indent(message, '> ')}\n - {ctx.target.author.mention}\n\n{response}"
    await ctx.send(content=r_format)


@message_context_menu(name="Check legit", dm_permission=False)
async def check_legit_function(ctx: ContextMenuContext):
    await ctx.defer()
    message = ctx.target.content
    # guild = utils.get(bot.guilds, id=ctx.guild_id)
    # channel = utils.get(guild.channels, id=guild_defaults[ctx.guild_id])

    convo = Conversation()
    convo.add_message(role='user', content=message + "\n\nIs this legit?")
    response = send_message(convo)
    r_format = f"{textwrap.indent(message, '> ')}\n - {ctx.target.author.mention}\n\n{response}"
    await ctx.send(content=r_format)


def send_message(conversation: Conversation):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.5,
        messages=conversation.get_messages(),
        # functions=[
        #     {
        #         "name": "search_arxiv",
        #         "description": "Search arXiv for papers",
        #         "parameters": {
        #             "type": "object",
        #             "properties": {
        #                 "query": {
        #                     "type": "string",
        #                     "description": "The query to search for"
        #                 },
        #                 "max_results": {
        #                     "type": "integer",
        #                     "description": "The maximum number of results to return"
        #                 },
        #                 "sort_by": {
        #                     "type": "string",
        #                     "description": "The field to sort by (relevance, lastUpdatedDate, submittedDate)"
        #                 }
        #             },
        #             "required": ["query"]
        #         }
        #     }
        # ],
        # function_call="auto"
    )

    if response.usage.total_tokens > 8192:
        # send_branched_message(conversation, message="Summarize the conversation.")
        while count_tokens(conversation=conversation) > 4096:
            conversation.pop_message()

    response_content = response.choices[0].message.content

    # if add_message:
    conversation.add_message(role='assistant', content=response_content)

    return response_content


def send_branched_message(conversation: Conversation, message: str):
    convo = Conversation()
    for messages in conversation.get_messages()[1:]:
        convo.add_message(role=messages['role'], content=messages['content'])
    convo.add_message(role='user', content=message)
    return send_message(convo)


def send_image_prompt(prompt):
    image_resp = client.images.generate(
        prompt=prompt,
        n=1,
        size="512x512"
    ).data[0].url
    return image_resp


def count_tokens(conversation):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    num_token = len(encoding.encode(conversation))
    return num_token


# def load_functions_descriptions():
#     functions = {}
#     functions[BaseFunction.get_name()] = BaseFunction.get_description()


# def arxiv_search(query: str, max_results: int = 10, sort_by: str = "relevance"):
#     sort_criterion = None
#     for criterion in arxiv.SortCriterion:
#         if criterion.value.lower() == sort_by.lower():
#             sort_criterion = criterion
#             break
#     if not sort_criterion:
#         raise ValueError(f"Invalid sort criterion: {sort_by}")
#     search = arxiv.Search(
#         query=query,
#         max_results=max_results,
#         sort_by=sort_criterion
#     )
#     results = []
#     for result in search.results():
#         result_dict = {
#             "title": result.title,
#             "authors": result.authors,
#             "summary": result.summary,
#             "published": result.published,
#             "updated": result.updated,
#             "arxiv_url": result.entry_id,
#             "pdf_url": result.pdf_url,
#             "doi": result.doi,
#         }
#         results.append(result_dict)
#     return results


if __name__ == '__main__':
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )

    intents = Intents.DEFAULT  # Set the intents to default
    intents.MESSAGE_CONTENTS = True  # Allow us to get the content of the message

    bot = Client(intents=Intents.DEFAULT)
    bot.start(token=os.getenv('DISCORD_TOKEN'))
