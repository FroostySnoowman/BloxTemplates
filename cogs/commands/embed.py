import discord
import yaml
from dataclasses import dataclass, field
from discord import app_commands
from discord.ext import commands

with open("config.yml", "r") as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
default_embed_color = data["General"].get("EMBED_COLOR", "#5865F2")


def parse_color(color_value: str) -> int | None:
    color_value = color_value.strip()
    if not color_value:
        return None

    if color_value.startswith("0x"):
        color_value = f"#{color_value[2:]}"

    try:
        return discord.Color.from_str(color_value).value
    except ValueError:
        return None


def parse_timestamp(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "on"}


def current_default_color() -> int:
    parsed = parse_color(default_embed_color)
    return parsed if parsed is not None else discord.Color.blurple().value


@dataclass
class EmbedFieldData:
    name: str
    value: str
    inline: bool = False


@dataclass
class EmbedDraft:
    content: str = ""
    title: str = ""
    description: str = ""
    url: str = ""
    color: int = field(default_factory=current_default_color)
    author_name: str = ""
    author_icon_url: str = ""
    footer_text: str = ""
    footer_icon_url: str = ""
    thumbnail_url: str = ""
    image_url: str = ""
    timestamp: bool = False
    fields: list[EmbedFieldData] = field(default_factory=list)

    def has_embed_payload(self) -> bool:
        return any(
            (
                self.title,
                self.description,
                self.url,
                self.author_name,
                self.footer_text,
                self.thumbnail_url,
                self.image_url,
                self.timestamp,
                len(self.fields) > 0,
            )
        )

    def to_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title or None,
            description=self.description or None,
            url=self.url or None,
            color=self.color,
        )

        if self.author_name:
            embed.set_author(name=self.author_name, icon_url=self.author_icon_url or None)
        if self.footer_text:
            embed.set_footer(text=self.footer_text, icon_url=self.footer_icon_url or None)
        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)
        if self.image_url:
            embed.set_image(url=self.image_url)
        if self.timestamp:
            embed.timestamp = discord.utils.utcnow()

        for field_data in self.fields[:25]:
            embed.add_field(name=field_data.name, value=field_data.value, inline=field_data.inline)

        return embed


class BasicEmbedModal(discord.ui.Modal, title="Edit Basic Embed"):
    def __init__(self, builder: "EmbedBuilderView"):
        super().__init__()
        self.builder = builder

        self.content = discord.ui.TextInput(
            label="Message Content (outside embed)",
            default=builder.draft.content,
            required=False,
            max_length=2000,
            style=discord.TextStyle.paragraph,
        )
        self.title_text = discord.ui.TextInput(
            label="Embed Title",
            default=builder.draft.title,
            required=False,
            max_length=256,
        )
        self.description = discord.ui.TextInput(
            label="Embed Description",
            default=builder.draft.description,
            required=False,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        self.color = discord.ui.TextInput(
            label="Embed Color (#5865F2)",
            default=f"#{builder.draft.color:06x}",
            required=False,
            max_length=16,
        )
        self.url = discord.ui.TextInput(
            label="Embed URL",
            default=builder.draft.url,
            required=False,
            max_length=1024,
        )

        self.add_item(self.content)
        self.add_item(self.title_text)
        self.add_item(self.description)
        self.add_item(self.color)
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.color.value.strip():
            parsed = parse_color(self.color.value)
            if parsed is None:
                await interaction.response.send_message(
                    "Invalid color. Use a hex color like `#5865F2`.",
                    ephemeral=True,
                )
                return
            self.builder.draft.color = parsed

        self.builder.draft.content = self.content.value.strip()
        self.builder.draft.title = self.title_text.value.strip()
        self.builder.draft.description = self.description.value.strip()
        self.builder.draft.url = self.url.value.strip()

        await interaction.response.send_message("Updated basic embed settings.", ephemeral=True)
        await self.builder.refresh_message()


class MediaEmbedModal(discord.ui.Modal, title="Edit Embed Media"):
    def __init__(self, builder: "EmbedBuilderView"):
        super().__init__()
        self.builder = builder

        self.thumbnail_url = discord.ui.TextInput(
            label="Thumbnail URL",
            default=builder.draft.thumbnail_url,
            required=False,
            max_length=1024,
        )
        self.image_url = discord.ui.TextInput(
            label="Image URL",
            default=builder.draft.image_url,
            required=False,
            max_length=1024,
        )

        self.add_item(self.thumbnail_url)
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.builder.draft.thumbnail_url = self.thumbnail_url.value.strip()
        self.builder.draft.image_url = self.image_url.value.strip()

        await interaction.response.send_message("Updated embed media settings.", ephemeral=True)
        await self.builder.refresh_message()


class MetaEmbedModal(discord.ui.Modal, title="Edit Embed Meta"):
    def __init__(self, builder: "EmbedBuilderView"):
        super().__init__()
        self.builder = builder

        self.author_name = discord.ui.TextInput(
            label="Author Name",
            default=builder.draft.author_name,
            required=False,
            max_length=256,
        )
        self.author_icon_url = discord.ui.TextInput(
            label="Author Icon URL",
            default=builder.draft.author_icon_url,
            required=False,
            max_length=1024,
        )
        self.footer_text = discord.ui.TextInput(
            label="Footer Text",
            default=builder.draft.footer_text,
            required=False,
            max_length=2048,
        )
        self.footer_icon_url = discord.ui.TextInput(
            label="Footer Icon URL",
            default=builder.draft.footer_icon_url,
            required=False,
            max_length=1024,
        )
        self.timestamp = discord.ui.TextInput(
            label="Timestamp? (yes/no)",
            default="yes" if builder.draft.timestamp else "no",
            required=False,
            max_length=16,
        )

        self.add_item(self.author_name)
        self.add_item(self.author_icon_url)
        self.add_item(self.footer_text)
        self.add_item(self.footer_icon_url)
        self.add_item(self.timestamp)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.builder.draft.author_name = self.author_name.value.strip()
        self.builder.draft.author_icon_url = self.author_icon_url.value.strip()
        self.builder.draft.footer_text = self.footer_text.value.strip()
        self.builder.draft.footer_icon_url = self.footer_icon_url.value.strip()
        self.builder.draft.timestamp = parse_timestamp(self.timestamp.value)

        await interaction.response.send_message("Updated embed metadata.", ephemeral=True)
        await self.builder.refresh_message()


class FieldsEmbedModal(discord.ui.Modal, title="Edit Embed Fields"):
    def __init__(self, builder: "EmbedBuilderView"):
        super().__init__()
        self.builder = builder

        default_fields = "\n".join(
            f"{entry.name} | {entry.value} | {'yes' if entry.inline else 'no'}"
            for entry in builder.draft.fields
        )
        self.fields_input = discord.ui.TextInput(
            label="One per line: name | value | inline",
            placeholder="Example: Rules | No spam links | yes",
            default=default_fields[:4000] if default_fields else None,
            required=False,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.fields_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_lines = [line.strip() for line in self.fields_input.value.splitlines() if line.strip()]
        parsed_fields: list[EmbedFieldData] = []

        if len(raw_lines) > 25:
            await interaction.response.send_message("You can only set up to 25 fields.", ephemeral=True)
            return

        for raw_line in raw_lines:
            parts = [part.strip() for part in raw_line.split("|")]
            if len(parts) < 2:
                await interaction.response.send_message(
                    f"Invalid field line: `{raw_line}`. Use `name | value | inline`.",
                    ephemeral=True,
                )
                return

            inline = parse_timestamp(parts[2]) if len(parts) >= 3 else False
            name = parts[0]
            value = parts[1]
            if not name or not value:
                await interaction.response.send_message(
                    f"Invalid field line: `{raw_line}`. Name and value are required.",
                    ephemeral=True,
                )
                return

            parsed_fields.append(EmbedFieldData(name=name, value=value, inline=inline))

        self.builder.draft.fields = parsed_fields
        await interaction.response.send_message("Updated embed fields.", ephemeral=True)
        await self.builder.refresh_message()


class EmbedBuilderView(discord.ui.View):
    def __init__(self, author_id: int, target_channel: discord.TextChannel):
        super().__init__(timeout=900)
        self.author_id = author_id
        self.target_channel = target_channel
        self.draft = EmbedDraft()
        self.message: discord.Message | None = None

    def builder_text(self) -> str:
        summary = [
            "**Embed Builder**",
            f"Target channel: {self.target_channel.mention}",
            f"Content: {'set' if self.draft.content else 'empty'}",
            f"Title: {'set' if self.draft.title else 'empty'}",
            f"Description: {'set' if self.draft.description else 'empty'}",
            f"Author: {'set' if self.draft.author_name else 'empty'}",
            f"Footer: {'set' if self.draft.footer_text else 'empty'}",
            f"Image: {'set' if self.draft.image_url else 'empty'}",
            f"Thumbnail: {'set' if self.draft.thumbnail_url else 'empty'}",
            f"Fields: {len(self.draft.fields)}",
            f"Timestamp: {'on' if self.draft.timestamp else 'off'}",
            f"Color: `#{self.draft.color:06x}`",
            "",
            "Use buttons to edit. `Preview` checks it first and `Send` posts it.",
        ]
        return "\n".join(summary)

    async def refresh_message(self) -> None:
        if self.message:
            await self.message.edit(content=self.builder_text(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who started this builder can use it.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.refresh_message()

    @discord.ui.button(label="Basic", style=discord.ButtonStyle.primary, row=0)
    async def basic(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(BasicEmbedModal(self))

    @discord.ui.button(label="Media", style=discord.ButtonStyle.secondary, row=0)
    async def media(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(MediaEmbedModal(self))

    @discord.ui.button(label="Meta", style=discord.ButtonStyle.secondary, row=0)
    async def meta(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(MetaEmbedModal(self))

    @discord.ui.button(label="Fields", style=discord.ButtonStyle.secondary, row=0)
    async def fields(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(FieldsEmbedModal(self))

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.success, row=1)
    async def preview(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.draft.content and not self.draft.has_embed_payload():
            await interaction.response.send_message(
                "This is currently empty. Add content or embed data first.",
                ephemeral=True,
            )
            return

        preview_payload = {}
        if self.draft.content:
            preview_payload["content"] = self.draft.content
        if self.draft.has_embed_payload():
            preview_payload["embed"] = self.draft.to_embed()

        await interaction.response.send_message(ephemeral=True, **preview_payload)

    @discord.ui.button(label="Send", style=discord.ButtonStyle.green, row=1)
    async def send(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.draft.content and not self.draft.has_embed_payload():
            await interaction.response.send_message(
                "This is currently empty. Add content or embed data first.",
                ephemeral=True,
            )
            return

        payload = {}
        if self.draft.content:
            payload["content"] = self.draft.content
        if self.draft.has_embed_payload():
            payload["embed"] = self.draft.to_embed()

        try:
            await self.target_channel.send(**payload)
        except discord.HTTPException as exc:
            await interaction.response.send_message(
                f"Failed to send embed: `{exc}`",
                ephemeral=True,
            )
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.send_message(
            f"Embed sent in {self.target_channel.mention}.",
            ephemeral=True,
        )
        await self.refresh_message()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True
        await interaction.response.send_message("Embed builder canceled.", ephemeral=True)
        await self.refresh_message()
        self.stop()


class EmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="embed", description="Build and send a custom embed with a UI editor.")
    @app_commands.describe(channel="Channel to send the finished embed to")
    @app_commands.default_permissions(manage_messages=True)
    async def embed(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("Please use this in a text channel.", ephemeral=True)
            return

        builder = EmbedBuilderView(author_id=interaction.user.id, target_channel=target_channel)
        await interaction.response.send_message(builder.builder_text(), view=builder, ephemeral=True)
        builder.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot), guilds=[discord.Object(id=guild_id)])