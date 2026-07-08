import asyncio
from io import BytesIO

from gtts import gTTS


async def synthesize_word(word: str, language: str) -> bytes:
    """Generate an MP3 pronunciation without blocking the bot event loop."""
    buffer = BytesIO()
    speech = gTTS(text=word, lang=language, slow=False)
    await asyncio.to_thread(speech.write_to_fp, buffer)
    return buffer.getvalue()
