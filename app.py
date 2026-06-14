import chainlit as cl
from agent import run_agent


@cl.on_chat_start
async def start():
    """Runs once when a user opens the chat."""
    await cl.Message(
        content="Welcome to Sērēnum 🌤️ Tell me where you are, and I'll tell you what your skin might need today."
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Runs every time the user sends a message."""
    
    # Show a thinking indicator while the agent works
    async with cl.Step(name="Checking weather & air quality..."):
        result = await cl.make_async(run_agent)(message.content)

    await cl.Message(content=result).send()