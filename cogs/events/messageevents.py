import discord
import aiohttp
import yaml
import time
import re
from discord.ext import commands
from collections import defaultdict, deque

with open("config.yml", "r") as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]

SPAM_WINDOW_SECONDS = 8
SPAM_MAX_MESSAGES = 5
REPEAT_WINDOW_SECONDS = 15
REPEAT_MAX_MESSAGES = 3

DISCORD_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:discord(?:app)?\.com|discord\.gg|discord\.gift)"
    r"/[^\s<>()]+",
    re.IGNORECASE,
)

GIFT_LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:discord\.gift|discord(?:app)?\.com/gifts)"
    r"/([a-zA-Z0-9]+)",
    re.IGNORECASE,
)

class MessageEventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_timestamps: dict[int, deque[float]] = defaultdict(deque)
        self.message_contents: dict[int, deque[tuple[float, str]]] = defaultdict(deque)
        self.gift_cache: dict[str, tuple[bool, float]] = {}

    async def _is_real_gift_code(self, code: str) -> bool:
        cache_key = code.lower()
        now = time.monotonic()
        cached = self.gift_cache.get(cache_key)
        if cached and now - cached[1] < 1800:
            return cached[0]

        url = (
            "https://discord.com/api/v10/entitlements/gift-codes/"
            f"{code}?with_application=false&with_subscription_plan=true"
        )

        is_real = False
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    is_real = response.status == 200
        except aiohttp.ClientError:
            is_real = False

        self.gift_cache[cache_key] = (is_real, now)
        return is_real

    async def _contains_blocked_discord_link(self, content: str) -> bool:
        links = DISCORD_LINK_RE.findall(content)
        if not links:
            return False

        for link in links:
            gift_match = GIFT_LINK_RE.match(link)
            if gift_match:
                code = gift_match.group(1)
                if await self._is_real_gift_code(code):
                    continue
            return True

        return False

    def _is_spam(self, message: discord.Message) -> bool:
        user_id = message.author.id
        now = time.monotonic()

        timestamps = self.message_timestamps[user_id]
        timestamps.append(now)
        while timestamps and now - timestamps[0] > SPAM_WINDOW_SECONDS:
            timestamps.popleft()
        if len(timestamps) >= SPAM_MAX_MESSAGES:
            return True

        normalized = re.sub(r"\s+", " ", message.content.lower()).strip()
        if not normalized:
            return False

        contents = self.message_contents[user_id]
        contents.append((now, normalized))
        while contents and now - contents[0][0] > REPEAT_WINDOW_SECONDS:
            contents.popleft()

        repeats = sum(1 for _, text in contents if text == normalized)
        return repeats >= REPEAT_MAX_MESSAGES

    async def _safe_delete(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.guild.id != guild_id:
            return
        if message.author.bot:
            return
        if message.author.guild_permissions.manage_messages:
            return

        if await self._contains_blocked_discord_link(message.content):
            await self._safe_delete(message)
            return

        if self._is_spam(message):
            await self._safe_delete(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageEventsCog(bot), guilds=[discord.Object(id=guild_id)])