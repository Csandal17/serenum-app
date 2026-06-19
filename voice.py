import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from langchain_anthropic import ChatAnthropic

load_dotenv()

# --- Configuration ---------------------------------------------------------
VOICE_ID = "E4IXevHtHpKGh0bvrPPr"   # Emilia, from your ElevenLabs library
MODEL_ID = "eleven_multilingual_v2"      # quality model (not the low-latency flash one)

eleven = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# A small, fast LLM call to turn a formatted brief into something speakable.
summariser = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=200,
)

SUMMARY_PROMPT = """You turn a written skincare brief into a short spoken version \
to be read aloud by a voice assistant.

Rules:
- 2 to 3 natural sentences, warm and calm.
- Plain spoken English only. No markdown, no tables, no bullet points, no emoji.
- Do NOT read out URLs or a "Sources" list.
- Lead with the location and the single most important action for today.
- Keep it under 60 words."""


def spoken_summary(brief_text: str) -> str:
    """Condense a formatted skin brief into a short, speech-friendly summary."""
    response = summariser.invoke([
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content": brief_text},
    ])
    return response.content.strip()


def synthesize(text: str) -> bytes:
    """Convert text to speech with ElevenLabs and return MP3 bytes."""
    audio = eleven.text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
    )
    # convert() returns a generator of byte chunks — join into one blob
    return b"".join(audio)


if __name__ == "__main__":
    sample = (
        "| Metric | Value |\n|---|---|\n| Temp | 21.8°C |\n| UV | 7 (High) |\n"
        "SPF is non-negotiable today. Humidity is comfortable, so keep hydration light.\n"
        "Sources: https://example.com"
    )
    summary = spoken_summary(sample)
    print("Spoken summary:", summary)
    audio_bytes = synthesize(summary)
    with open("voice_module_test.mp3", "wb") as f:
        f.write(audio_bytes)
    print("Saved voice_module_test.mp3")