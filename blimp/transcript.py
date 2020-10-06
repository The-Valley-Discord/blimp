import html
import re
from datetime import timedelta
from string import Template
from typing import List

import discord


def shrink(string):
    "Remove whitespace from a string"
    return re.sub(r"\n\s*", "", string)


class Transcript:
    "Create a transcript of a channel."

    @staticmethod
    def fancify_content(content):
        "Faithfully recreate discord's markup in HTML. absolutely disgusting"
        content = html.escape(content)

        def emojify(match):
            return (
                f"<img src='https://cdn.discordapp.com/emojis/{match[3]}"
                + (".gif" if match[1] == "a" else ".png")
                + f"' class='emoji' title='{match[2]}'>"
            )

        content = re.sub(r"&lt;(a?):(\w+):(\d+)&gt;", emojify, content)

        content = re.sub(r"```(.+)```", r"<pre>\1</pre>", content, flags=re.DOTALL)
        # advanced[tm] markdown processing
        content = content.replace("\n", "<br>")
        content = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", content)
        content = re.sub(r"\*([^\*]+)\*", r"<i>\1</i>", content)
        content = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", content)
        content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)
        return content

    TRANSCRIPT_HEADER = Template(
        shrink(
            """
            <!doctype html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>#$channelname</title>
                <style>
                    body {
                        background: #36393f;
                        color: #dcddde;
                        font-family: Roboto, sans-serif;
                    }
                    .message-container {
                        margin: 1rem 0;
                        display: grid;
                        grid-template-columns: 3rem auto;
                        grid-template-rows: 1.3rem auto;
                        grid-column-gap: 1rem;
                        border-left: 3px solid #36393f;
                        padding-left: 5px;
                        min-height: 2.6rem;
                    }
                    .message-container .metadata {
                        grid-column: 2;
                        grid-row: 1;
                    }
                    .message-container .metadata * {
                        color: #72767d;
                        font-size: .8rem;
                    }
                    .message-container .metadata .author {
                        font-size: 1rem;
                        color: #dcddde;
                        margin-right: .3rem;
                        font-weight: bold;
                    }
                    .message-container .metadata .id-anchor {
                        text-decoration: none;
                    }
                    .message-container .metadata .id-anchor:hover {
                        text-decoration: underline;
                    }
                    .message-container img.avatar {
                        grid-column: 1;
                        width: 3rem;
                        border-radius: 50%;
                    }
                    .message-container .content {
                        max-width: 75ch;
                        overflow-wrap: anywhere;
                        line-height: 1.3rem;
                        grid-column: 2;
                    }
                    .content a {
                        color: #00b0f4;
                    }
                    .content pre, content code {
                        font-size: .8rem;
                        background: #2f3136;
                        padding: .3rem;
                        overflow-wrap: anywhere;
                        font-family: monospace;
                    }
                    .content img.emoji {
                        height: 1.3rem;
                        vertical-align: middle;
                    }
                    .content img.emoji.emoji-big {
                        height: 2.6rem;
                    }
                    .content img.attachment {
                        display: block;
                        max-width: 32em;
                    }
                    .embed {
                        max-width: 32rem;
                        border: 3px solid #2f3136;
                        background: #2f3136;
                        border-radius: .3rem;
                        border-left: 3px solid;
                        padding: .1rem;
                    }
                    .embed * {
                        margin: 0.3rem;
                        padding: 0;
                    }
                </style>
            </head>
            <body>
                <h1>$headline</h1>
                <section>
            """
        )
    )

    TRANSCRIPT_ITEM = Template(
        shrink(
            """
            <div class="message-container" id="$messageid">
                <img class="avatar" src="$authoravatar">
                <div class="metadata">
                    <span class="author" title="$authortag">$authornick </span>
                    <span class="timestamp">$timestamp </span>
                    <a href="#$messageid" class="id-anchor">$messageid</a>
                </div>
                <div class="content">$content</div>
            </div>
            """
        )
    )

    TRANSCRIPT_FOOTER = "</section></body></html>"

    @classmethod
    def write_embed(cls, embed: discord.Embed) -> str:
        "Render an embed to HTML. TODO more than bare minimum of effort"

        result = "<div class='embed' "
        if embed.color:
            result += f"style='border-left-color: #{str(hex(embed.color.value))[2:]}'>"

        if embed.title:
            result += "<h3>"
            if embed.url:
                result += f"<a href='{embed.url}'>{embed.title}</a>"
            else:
                result += embed.title
            result += "</h3>"

        if embed.description:
            result += f"<p>{cls.fancify_content(embed.description)}</p>"

        result += "</div>"
        return result

    @classmethod
    async def write_transcript(cls, file, channel) -> List[discord.Message]:
        "Write a transcript of the channel into file and return a list of all messages processed."
        all_messages = []
        file.write(
            cls.TRANSCRIPT_HEADER.substitute(
                channelname=channel.name,
                headline=f"#{channel.name} on {channel.guild.name}",
            )
        )
        async for message in channel.history(limit=None, oldest_first=True):
            all_messages.append(message)
            clean_timestamp = message.created_at - timedelta(
                microseconds=message.created_at.microsecond
            )
            file.write(
                cls.TRANSCRIPT_ITEM.substitute(
                    messageid=message.id,
                    authortag=str(message.author),
                    authornick=message.author.display_name,
                    authoravatar=message.author.avatar_url,
                    timestamp=clean_timestamp,
                    content=cls.fancify_content(message.clean_content)
                    + "\n".join(
                        [
                            f"<img src='{a.url}' class='attachment' title='{a.filename}'>"
                            for a in message.attachments
                        ]
                    )
                    + "\n".join(
                        [cls.write_embed(e) for e in message.embeds if e.type == "rich"]
                    ),
                )
            )
        file.write(cls.TRANSCRIPT_FOOTER)

        return all_messages
