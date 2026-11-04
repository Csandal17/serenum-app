import logging

import chainlit as cl
from agent import run_agent
from text_filters import remove_em_dashes
from voice import spoken_summary, synthesize

log = logging.getLogger("serenum")


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="🌤️ My skin brief today",
            message="Give me today's skin brief for London",
        ),
        cl.Starter(
            label="🌍 Travel mode",
            message="I'm travelling to Barcelona next week. What will the conditions be like?",
        ),
        cl.Starter(
            label="🌿 What sources say today",
            message="Check London's weather today, then tell me what trusted UK sources say about skin in those conditions.",
        ),
        cl.Starter(
            label="🔬 Myth buster",
            message="Can you get sunburnt on a cloudy day?",
        ),
    ]


@cl.on_message
async def main(message: cl.Message):
    """Runs every time the user sends a message."""
    try:
        async with cl.Step(name="Checking conditions and sources..."):
            result = await cl.make_async(run_agent)(message.content)
    except Exception:
        log.exception("The agent failed")
        await cl.Message(
            content="Sērēnum couldn't answer just now. Please try again in a moment."
        ).send()
        return

    # Attach an on-demand Listen button that carries the response text
    listen_action = cl.Action(
        name="listen",
        payload={"text": result},
        label="Listen",
        icon="volume-2",
    )

    await cl.Message(content=result, actions=[listen_action]).send()


@cl.action_callback("listen")
async def on_listen(action: cl.Action):
    """Generate and play a spoken version of the answer on demand."""
    brief_text = action.payload["text"]

    try:
        async with cl.Step(name="Generating audio..."):
            summary = remove_em_dashes(await cl.make_async(spoken_summary)(brief_text))
            audio_bytes = await cl.make_async(synthesize)(summary)

        audio = cl.Audio(
            content=audio_bytes,
            name="skin_brief.mp3",
            display="inline",
            auto_play=True,
        )
        await cl.Message(content=summary, elements=[audio]).send()

    except Exception:
        log.exception("Listen failed")
        await cl.Message(content="Sorry, I couldn't generate the audio just now.").send()
