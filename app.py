import chainlit as cl
from agent import run_agent
from voice import spoken_summary, synthesize


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="🌤️ My skin brief today",
            message="Give me my skin brief for London",
        ),
        cl.Starter(
            label="🌍 Travel mode",
            message="I'm travelling to Barcelona next week — how should I adjust my skincare routine?",
        ),
        cl.Starter(
            label="🌿 Build my routine",
            message="Build me an AM and PM skincare routine for London's climate today",
        ),
        cl.Starter(
            label="🔬 Myth buster",
            message="Does drinking water actually hydrate your skin?",
        ),
    ]


@cl.on_message
async def main(message: cl.Message):
    """Runs every time the user sends a message."""
    async with cl.Step(name="Checking weather & air quality..."):
        result = await cl.make_async(run_agent)(message.content)

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
    """Generate and play a spoken version of the brief on demand."""
    brief_text = action.payload["text"]

    try:
        async with cl.Step(name="Generating audio..."):
            summary = await cl.make_async(spoken_summary)(brief_text)
            audio_bytes = await cl.make_async(synthesize)(summary)

        audio = cl.Audio(
            content=audio_bytes,
            name="skin_brief.mp3",
            display="inline",
            auto_play=True,
        )
        await cl.Message(content=summary, elements=[audio]).send()

    except Exception as e:
        await cl.Message(
            content=f"Sorry — I couldn't generate the audio just now. ({e})"
        ).send()
        