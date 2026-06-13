import chainlit as cl


@cl.on_chat_start
async def start():
    """Runs once when a user opens the chat."""
    await cl.Message(
        content="Welcome to Sērēnum 🌤️ Tell me where you are and I'll tell you what your skin might need today."
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Runs every time the user sends a message."""
    await cl.Message(
        content=f"You said: {message.content} — skin advice coming soon!"
    ).send()
