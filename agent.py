import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from tools import get_weather, get_air_quality, get_uv_index

load_dotenv()


@tool
def weather_tool(city: str) -> dict:
    """Get current weather for a city including temperature, humidity, wind speed, and conditions."""
    return get_weather(city)


@tool
def air_quality_tool(lat: float, lon: float) -> dict:
    """Get air quality data for a location using latitude and longitude. Returns AQI index and PM2.5."""
    return get_air_quality(lat, lon)


@tool
def uv_tool(lat: float, lon: float) -> dict:
    """Get the current UV index for a location using latitude and longitude."""
    return get_uv_index(lat, lon)


tools = [weather_tool, air_quality_tool, uv_tool]

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
).bind_tools(tools)

SYSTEM_PROMPT = """You are Sērēnum, a skincare advisor that translates weather data into personalised skin advice.

When a user gives you a location:
1. Call the weather tool to get current conditions
2. Use the latitude and longitude from weather to call the air quality tool  
3. Use the same coordinates to call the UV index tool
4. Combine all three data points into a concise skin brief

Your skin brief should cover:
- SPF recommendation based on UV index
- Hydration advice based on humidity and temperature
- Barrier protection advice based on AQI and PM2.5
- Any active ingredients to avoid or embrace today

Keep advice practical, warm, and under 150 words. Never claim to diagnose skin conditions."""


def run_agent(user_input: str) -> str:
    """Run the Sērēnum agent with a user message and return the skin brief."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    # Agentic loop — keep calling tools until the LLM is done
    while True:
        response = llm.invoke(messages)
        messages.append(response)

        # If no tool calls, we have the final answer
        if not response.tool_calls:
            return response.content

        # Execute each tool the LLM requested
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            # Find and run the matching tool
            tool_fn = next(t for t in tools if t.name == tool_name)
            tool_result = tool_fn.invoke(tool_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": str(tool_result),
            })


if __name__ == "__main__":
    result = run_agent("I'm in London. What does my skin need today?")
    print("\n--- SKIN BRIEF ---")
    print(result)
    