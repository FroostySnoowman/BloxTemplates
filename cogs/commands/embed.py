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
    text = color_value.strip()
    if not text:
        return None

    if text.startswith("0x"):
        text = f"#{text[2:]}"

    try:
        return discord.Color.from_str(text).value
    except ValueError:
        return None


def parse_toggle(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "on", "inline"}


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

    def build_embed(self) -> discord.Embed | None:
        if not self.has_embed_payload():
            return None

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

    def send_payload(self) -> dict:
        payload = {}
        if self.content:
            payload["content"] = self.content

        embed = self.build_embed()
        if embed is not None:
            payload["embed"] = embed

        return payload


class SingleValueModal(discord.ui.Modal):
    def __init__(
        self,
        builder: "EmbedBuilderView",
        *,
        title: str,
        field_label: str,
        current_value: str,
        success_label: str,
        max_length: int,
        text_style: discord.TextStyle = discord.TextStyle.short,
        placeholder: str = "",
        color_mode: bool = False,
    ):
        super().__init__(title=title)
        self.builder = builder
        self.success_label = success_label
        self.color_mode = color_mode

        self.input_value = discord.ui.TextInput(
            label=field_label,
            default=current_value,
            required=False,
            max_length=max_length,
            style=text_style,
            placeholder=placeholder,
        )
        self.add_item(self.input_value)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_value = self.input_value.value.strip()

        if self.color_mode:
            if not raw_value:
                self.builder.draft.color = current_default_color()
            else:
                parsed = parse_color(raw_value)
                if parsed is None:
                    await interaction.response.send_message(
                        "Invalid color. Use hex like `#5865F2`.",
                        ephemeral=True,
                    )
                    return
                self.builder.draft.color = parsed
        else:
            setattr(self.builder.draft, self.success_label, raw_value)

        await interaction.response.send_message("Updated.", ephemeral=True)
        await self.builder.refresh_message()


class FieldSlotModal(discord.ui.Modal):
    def __init__(self, builder: "EmbedBuilderView", index: int):
        super().__init__(title=f"Edit Field {index + 1}")
        self.builder = builder
        self.index = index

        existing = builder.draft.fields[index] if index < len(builder.draft.fields) else None
        self.field_name = discord.ui.TextInput(
            label="Field Name",
            default=existing.name if existing else "",
            required=False,
            max_length=256,
        )
        self.field_value = discord.ui.TextInput(
            label="Field Value",
            default=existing.value if existing else "",
            required=False,
            max_length=1024,
            style=discord.TextStyle.paragraph,
        )
        self.field_inline = discord.ui.TextInput(
            label="Inline? (yes/no)",
            default="yes" if existing and existing.inline else "no",
            required=False,
            max_length=16,
        )
        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.field_inline)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.field_name.value.strip()
        value = self.field_value.value.strip()
        inline = parse_toggle(self.field_inline.value)
        fields = self.builder.draft.fields

        if not name and not value:
            if self.index < len(fields):
                fields.pop(self.index)
            await interaction.response.send_message("Field cleared.", ephemeral=True)
            await self.builder.refresh_message()
            return

        if not name or not value:
            await interaction.response.send_message(
                "Both field name and field value are required.",
                ephemeral=True,
            )
            return

        if self.index > len(fields):
            await interaction.response.send_message(
                f"Fill Field {len(fields) + 1} first.",
                ephemeral=True,
            )
            return

        field_data = EmbedFieldData(name=name, value=value, inline=inline)
        if self.index == len(fields):
            if len(fields) >= 25:
                await interaction.response.send_message(
                    "Discord only allows 25 embed fields.",
                    ephemeral=True,
                )
                return
            fields.append(field_data)
        else:
            fields[self.index] = field_data

        await interaction.response.send_message("Field updated.", ephemeral=True)
        await self.builder.refresh_message()


class BulkFieldsModal(discord.ui.Modal, title="Bulk Edit Fields"):
    def __init__(self, builder: "EmbedBuilderView"):
        super().__init__()
        self.builder = builder

        default_fields = "\n".join(
            f"{entry.name} | {entry.value} | {'yes' if entry.inline else 'no'}"
            for entry in builder.draft.fields
        )
        self.fields_input = discord.ui.TextInput(
            label="name | value | inline (one per line)",
            placeholder="Rules | No spam links | yes",
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
                    f"Invalid line: `{raw_line}`. Use `name | value | inline`.",
                    ephemeral=True,
                )
                return

            name = parts[0]
            value = parts[1]
            inline = parse_toggle(parts[2]) if len(parts) >= 3 else False
            if not name or not value:
                await interaction.response.send_message(
                    f"Invalid line: `{raw_line}`. Name and value are required.",
                    ephemeral=True,
                )
                return

            parsed_fields.append(EmbedFieldData(name=name, value=value, inline=inline))

        self.builder.draft.fields = parsed_fields
        await interaction.response.send_message("Fields updated.", ephemeral=True)
        await self.builder.refresh_message()


class SubmitChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select a channel to submit/send this embed",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, EmbedBuilderView):
            await interaction.response.send_message("Builder state not found.", ephemeral=True)
            return
        await view.submit_to_channel(interaction, self.values[0])


class ActionButton(discord.ui.Button):
    def __init__(self, action: str, label: str, style: discord.ButtonStyle, row: int):
        super().__init__(label=label, style=style, row=row)
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, EmbedBuilderView):
            await interaction.response.send_message("Builder state not found.", ephemeral=True)
            return
        await view.handle_action(interaction, self.action)


class EmbedBuilderView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=900)
        self.author_id = author_id
        self.draft = EmbedDraft()
        self.message: discord.Message | None = None
        self.submitted_to: str = "Not submitted yet"

        self.add_item(SubmitChannelSelect())

        layout = [
            ("content", "Content", discord.ButtonStyle.primary, 1),
            ("title", "Title", discord.ButtonStyle.primary, 1),
            ("description", "Description", discord.ButtonStyle.primary, 1),
            ("url", "URL", discord.ButtonStyle.primary, 1),
            ("color", "Color", discord.ButtonStyle.primary, 1),
            ("author_name", "Author Name", discord.ButtonStyle.secondary, 2),
            ("author_icon_url", "Author Icon", discord.ButtonStyle.secondary, 2),
            ("footer_text", "Footer Text", discord.ButtonStyle.secondary, 2),
            ("footer_icon_url", "Footer Icon", discord.ButtonStyle.secondary, 2),
            ("thumbnail_url", "Thumbnail", discord.ButtonStyle.secondary, 2),
            ("image_url", "Image", discord.ButtonStyle.secondary, 3),
            ("toggle_timestamp", "Timestamp", discord.ButtonStyle.secondary, 3),
            ("fields_bulk", "Fields Bulk", discord.ButtonStyle.secondary, 3),
            ("field_1", "Field 1", discord.ButtonStyle.success, 3),
            ("field_2", "Field 2", discord.ButtonStyle.success, 3),
            ("field_3", "Field 3", discord.ButtonStyle.success, 4),
            ("field_4", "Field 4", discord.ButtonStyle.success, 4),
            ("field_5", "Field 5", discord.ButtonStyle.success, 4),
            ("field_6", "Field 6", discord.ButtonStyle.success, 4),
            ("field_7", "Field 7", discord.ButtonStyle.success, 4),
        ]

        for action, label, style, row in layout:
            self.add_item(ActionButton(action=action, label=label, style=style, row=row))

    def status_text(self) -> str:
        content_preview = self.draft.content if self.draft.content else "empty"
        if len(content_preview) > 100:
            content_preview = f"{content_preview[:97]}..."

        return "\n".join(
            [
                "**Embed Builder (Live Preview)**",
                "Use the channel dropdown above the buttons to submit.",
                f"Submitted: {self.submitted_to}",
                f"Content preview: {content_preview}",
                f"Title: {'set' if self.draft.title else 'empty'}",
                f"Description: {'set' if self.draft.description else 'empty'}",
                f"Author: {'set' if self.draft.author_name else 'empty'}",
                f"Footer: {'set' if self.draft.footer_text else 'empty'}",
                f"Image: {'set' if self.draft.image_url else 'empty'}",
                f"Thumbnail: {'set' if self.draft.thumbnail_url else 'empty'}",
                f"Fields: {len(self.draft.fields)} / 25",
                f"Timestamp: {'on' if self.draft.timestamp else 'off'}",
                f"Color: `#{self.draft.color:06x}`",
            ]
        )

    async def refresh_message(self) -> None:
        if self.message is None:
            return

        await self.message.edit(
            content=self.status_text(),
            embed=self.draft.build_embed(),
            view=self,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command user can edit this builder.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.refresh_message()

    async def handle_action(self, interaction: discord.Interaction, action: str) -> None:
        if action.startswith("field_"):
            field_number = int(action.split("_")[1])
            await interaction.response.send_modal(FieldSlotModal(self, field_number - 1))
            return

        if action == "toggle_timestamp":
            self.draft.timestamp = not self.draft.timestamp
            await interaction.response.send_message(
                f"Timestamp {'enabled' if self.draft.timestamp else 'disabled'}.",
                ephemeral=True,
            )
            await self.refresh_message()
            return

        if action == "fields_bulk":
            await interaction.response.send_modal(BulkFieldsModal(self))
            return

        modal_map = {
            "content": SingleValueModal(
                self,
                title="Edit Message Content",
                field_label="Content (outside embed)",
                current_value=self.draft.content,
                success_label="content",
                max_length=2000,
                text_style=discord.TextStyle.paragraph,
            ),
            "title": SingleValueModal(
                self,
                title="Edit Embed Title",
                field_label="Title",
                current_value=self.draft.title,
                success_label="title",
                max_length=256,
            ),
            "description": SingleValueModal(
                self,
                title="Edit Embed Description",
                field_label="Description",
                current_value=self.draft.description,
                success_label="description",
                max_length=4000,
                text_style=discord.TextStyle.paragraph,
            ),
            "url": SingleValueModal(
                self,
                title="Edit Embed URL",
                field_label="URL",
                current_value=self.draft.url,
                success_label="url",
                max_length=1024,
                placeholder="https://example.com",
            ),
            "color": SingleValueModal(
                self,
                title="Edit Embed Color",
                field_label="Hex Color (blank resets default)",
                current_value=f"#{self.draft.color:06x}",
                success_label="color",
                max_length=16,
                placeholder="#5865F2",
                color_mode=True,
            ),
            "author_name": SingleValueModal(
                self,
                title="Edit Author Name",
                field_label="Author Name",
                current_value=self.draft.author_name,
                success_label="author_name",
                max_length=256,
            ),
            "author_icon_url": SingleValueModal(
                self,
                title="Edit Author Icon URL",
                field_label="Author Icon URL",
                current_value=self.draft.author_icon_url,
                success_label="author_icon_url",
                max_length=1024,
            ),
            "footer_text": SingleValueModal(
                self,
                title="Edit Footer Text",
                field_label="Footer Text",
                current_value=self.draft.footer_text,
                success_label="footer_text",
                max_length=2048,
            ),
            "footer_icon_url": SingleValueModal(
                self,
                title="Edit Footer Icon URL",
                field_label="Footer Icon URL",
                current_value=self.draft.footer_icon_url,
                success_label="footer_icon_url",
                max_length=1024,
            ),
            "thumbnail_url": SingleValueModal(
                self,
                title="Edit Thumbnail URL",
                field_label="Thumbnail URL",
                current_value=self.draft.thumbnail_url,
                success_label="thumbnail_url",
                max_length=1024,
            ),
            "image_url": SingleValueModal(
                self,
                title="Edit Image URL",
                field_label="Image URL",
                current_value=self.draft.image_url,
                success_label="image_url",
                max_length=1024,
            ),
        }

        modal = modal_map.get(action)
        if modal is None:
            await interaction.response.send_message("Unknown editor action.", ephemeral=True)
            return

        await interaction.response.send_modal(modal)

    async def submit_to_channel(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Please choose a text channel.", ephemeral=True)
            return

        payload = self.draft.send_payload()
        if not payload:
            await interaction.response.send_message(
                "This embed is empty. Add content or embed data first.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me if interaction.guild else None
        if bot_member is None:
            await interaction.response.send_message("I could not verify my permissions.", ephemeral=True)
            return

        perms = channel.permissions_for(bot_member)
        if not perms.send_messages:
            await interaction.response.send_message(
                f"I can't send messages in {channel.mention}.",
                ephemeral=True,
            )
            return
        if "embed" in payload and not perms.embed_links:
            await interaction.response.send_message(
                f"I need `Embed Links` permission in {channel.mention}.",
                ephemeral=True,
            )
            return

        try:
            await channel.send(**payload)
        except discord.HTTPException as exc:
            await interaction.response.send_message(
                f"Failed to send embed: `{exc}`",
                ephemeral=True,
            )
            return

        self.submitted_to = channel.mention
        for item in self.children:
            item.disabled = True

        await interaction.response.send_message(f"Embed sent to {channel.mention}.", ephemeral=True)
        await self.refresh_message()
        self.stop()


class EmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="embed", description="Live embed builder with direct part-by-part buttons.")
    @app_commands.default_permissions(manage_messages=True)
    async def embed(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        builder = EmbedBuilderView(author_id=interaction.user.id)
        response_payload = {
            "content": builder.status_text(),
            "view": builder,
            "ephemeral": True,
        }
        preview_embed = builder.draft.build_embed()
        if preview_embed is not None:
            response_payload["embed"] = preview_embed

        await interaction.response.send_message(**response_payload)
        builder.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot), guilds=[discord.Object(id=guild_id)])
