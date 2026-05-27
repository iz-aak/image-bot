import discord
import aiohttp
import base64
import time
import os
from groq import Groq

# ── config ──────────────────────────────────────────────────
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GROQ_API_KEY  = os.environ["GROQ_API_KEY"]
CHANNEL_ID    = int(os.environ["CHANNEL_ID"])  # only watch this channel
# ────────────────────────────────────────────────────────────

EMBED_COLOR = 0x66FF00
MODEL       = "meta-llama/llama-4-scout-17b-16e-instruct"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
groq   = Groq(api_key=GROQ_API_KEY)


def loading_embed() -> discord.Embed:
    e = discord.Embed(description="# Loading...", color=EMBED_COLOR)
    e.set_footer(text="zenith image bot")
    return e


def answer_embed(answer: str, elapsed: int) -> discord.Embed:
    e = discord.Embed(
        description=f"Answer:\n# ```{answer}```\n-# zenith image bot • {elapsed}s",
        color=EMBED_COLOR,
    )
    return e


def error_embed(elapsed: int) -> discord.Embed:
    e = discord.Embed(
        description=f"# Couldn't read question\n-# zenith image bot • {elapsed}s",
        color=0xFF3333,
    )
    return e


async def fetch_image_b64(url: str) -> tuple[str, str]:
    """Download attachment and return (base64_data, media_type)."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
            ct   = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    return base64.b64encode(data).decode(), ct


async def ask_groq(b64: str, media_type: str) -> str:
    """Send image to Groq and return the answer string."""
    completion = groq.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "You are a homework assistant. "
                            "Look at this maths or science question and give ONLY the final answer — "
                            "no working, no explanation, no punctuation beyond what's needed for the answer itself. "
                            "If there are multiple answers (e.g. quadratic roots), list them separated by commas. "
                            "Example good responses: '42', 'x = 3, x = -1', '9.81 m/s²'. "
                            "If you cannot read the question clearly, reply with exactly: UNREADABLE"
                        ),
                    },
                ],
            }
        ],
        max_tokens=200,
    )
    return completion.choices[0].message.content.strip()


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} — watching channel {CHANNEL_ID}")


@client.event
async def on_message(message: discord.Message):
    # ignore bots, wrong channel, no attachments
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return
    if not message.attachments:
        return

    # find first image attachment
    image = next(
        (a for a in message.attachments if a.content_type and a.content_type.startswith("image/")),
        None,
    )
    if not image:
        return

    start = time.time()

    # send loading embed as a reply immediately
    reply = await message.reply(embed=loading_embed(), mention_author=False)

    try:
        b64, media_type = await fetch_image_b64(image.url)
        answer          = await ask_groq(b64, media_type)
        elapsed         = int(time.time() - start)

        if answer == "UNREADABLE":
            await reply.edit(embed=error_embed(elapsed))
        else:
            await reply.edit(embed=answer_embed(answer, elapsed))

    except Exception as exc:
        elapsed = int(time.time() - start)
        print(f"Error: {exc}")
        await reply.edit(embed=error_embed(elapsed))


client.run(DISCORD_TOKEN)
