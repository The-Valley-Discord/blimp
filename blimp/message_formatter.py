import discord
from toml import TomlDecodeError, loads

from .customizations import Blimp


def create_message_dict(text: str, channel: discord.TextChannel) -> dict:
    "Turn a string into a dict that can be deconstructed into a message create/edit call."

    try:
        return message_dict_from_toml(loads(text), channel)
    except TomlDecodeError:
        return {"content": text}


def message_dict_from_toml(toml: dict, channel: discord.TextChannel) -> dict:
    "Turn a TOML-supplied dict into message create/edit call dict."
    output = {"content": toml.get("content")}

    if toml.get("reference"):
        output["reference"] = discord.MessageReference(
            message_id=int(toml["reference"]), channel_id=channel.id
        )

    embed_data = toml.get("embed")
    if embed_data:
        output["embed"] = discord.Embed(
            title=embed_data.get("title"),
            description=embed_data.get("description"),
            url=embed_data.get("url"),
        )

        color = embed_data.get("color")
        if color and isinstance(color, int) and color in range(0, (0xFF_FF_FF + 1)):
            output["embed"].color = color
        elif isinstance(color, str) and color in dir(Blimp.Context.Color):
            output["embed"].color = Blimp.Context.Color[color]

        footer = embed_data.get("footer")
        if isinstance(footer, dict):
            output["embed"].set_footer(
                text=footer.get("text"),
                icon_url=footer.get("icon_url"),
            )

        image = embed_data.get("image_url")
        if isinstance(image, str):
            output["embed"].set_image(url=image)

        thumbnail = embed_data.get("thumbnail_url")
        if isinstance(thumbnail, str):
            output["embed"].set_thumbnail(url=thumbnail)

        author = embed_data.get("author")
        if isinstance(author, dict):
            output["embed"].set_author(
                name=author.get("name"),
                icon_url=author.get("icon_url"),
            )

        fields = embed_data.get("fields")
        if isinstance(fields, list):
            for field in fields:
                output["embed"].add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False),
                )

    return output
