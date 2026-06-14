import chainlit as cl
from agent import run_agent


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

    await cl.Message(content=result).send()
    