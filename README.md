---
title: Sērēnum
emoji: 💧
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Sērēnum

**An AI skincare companion that reads live weather and shows what trusted UK sources say about skin.**

🔗 **[Try it live](https://huggingface.co/spaces/Csandal17/serenum)**

Tell Sērēnum where you are, and it reads the current UV index, humidity, temperature and air quality for your location, then shows what trusted UK health sources say about skin in those conditions. You can also ask it skincare myth and science questions, and it answers only from the NHS, NICE and the British Association of Dermatologists, with every source linked.

---

## The brief, and the spin

Sērēnum started from a simple prompt: build a *Smart Weather Assistant*: an AI agent that delivers real-time conditions and personalised suggestions.

Most takes on that brief suggest activities ("good day for a run"). Mine went somewhere I actually care about. Weather doesn't just decide whether to bring an umbrella. It quietly shapes what your skin is dealing with. High UV with cloud cover still burns. Low humidity pulls moisture out of your skin. Poor air quality stresses your barrier. Sērēnum turns the same live weather data into skincare information that responds to the day in front of you.

For today, it works off **real-time** data, so the brief reflects conditions right now, which is exactly when you're deciding what to put on your face. For trips, it uses a daily forecast up to 14 days ahead.

---

## What it does

- **Skin brief:** today's UV, humidity, temperature and air quality, with what trusted sources say about the most notable condition.
- **Travel mode:** the daily forecast for somewhere you're heading, up to 14 days ahead.
- **What sources say today:** today's conditions first, then what trusted UK sources say about skin in them.
- **Myth buster:** ask about a skincare claim ("can you get sunburnt on a cloudy day?") and see what trusted sources say, with every source linked. If none of them cover it, Sērēnum says so.
- **Listen:** tap to hear a short spoken version of any answer, narrated in a calm voice. Built for the getting-ready-in-the-morning moment, when reading a screen isn't always practical.

---

## Trusted sources only

Sērēnum's evidence search is limited to four sites: `nhs.uk`, `nice.org.uk`, `bad.org.uk` and `skinhealthinfo.org.uk` (the British Association of Dermatologists' patient site). The list lives in one place, `sources.py`, and every search result is checked against it in code, so a page from anywhere else is never cited.

Sērēnum describes conditions and what those sources say. It doesn't give personal advice, diagnose skin conditions, or recommend products, and it points questions about a specific condition to a GP or pharmacist.

---

## Why weather?

Three live signals do most of the work:

- **UV index** drives the single most important decision of the day: sun protection. It stays high under cloud, which is why a brief beats a glance out the window.
- **Humidity and temperature** shape hydration. Dry, cold air calls for richer occlusives; warm, humid air calls for lighter layers.
- **Air quality (AQI / PM2.5)** affects the skin barrier. Pollution is an oxidative stressor, which is where antioxidants like vitamin C earn their place.

Sērēnum combines all three into one picture rather than three disconnected facts.

---

## Architecture

```
        User  (Chainlit chat UI, custom-branded)
          │
          ▼
   LangChain agent  ◄───  Claude (Anthropic API): reasoning and tool choice
          │
          ├─ weather_tool ─────────►  OpenWeatherMap  (temp, humidity, conditions)
          ├─ air_quality_tool ─────►  OpenWeatherMap  (AQI, PM2.5)
          ├─ uv_tool ──────────────►  OpenWeatherMap  (UV index)
          ├─ forecast_tool ────────►  Open-Meteo      (daily forecast for trips)
          └─ evidence_search_tool ─►  Tavily          (NHS, NICE and BAD only)
          │
          ▼
     Answer (text, em dashes removed)
          │
          └─ "Listen" ─►  spoken_summary (Claude) ─►  ElevenLabs TTS ─►  audio
```

The agent uses a tool-calling loop: Claude decides which tools to call, runs them, and synthesises the results into the answer. It stops after 8 rounds of tool calls, so a stuck loop can't keep spending credit, and a failed tool comes back to Claude as a plain message rather than crashing the app. Every answer then has any em dashes removed in code (`text_filters.py`), so the rule doesn't depend on the model remembering it. The Listen feature is deliberately a two-step pipeline: a formatted brief (with tables and source links) doesn't read well aloud, so a short *speech-friendly* summary is generated first, then voiced.

---

## Tech stack

- **Agent framework:** LangChain (tool-calling loop with `.bind_tools()`)
- **Reasoning:** Anthropic API (Claude)
- **UI:** Chainlit (custom theme, branding, and `Listen` action)
- **Weather data:** OpenWeatherMap (current weather, UV, air quality) and Open-Meteo (trip forecasts)
- **Evidence search:** Tavily, limited to trusted UK sources
- **Voice:** ElevenLabs (text-to-speech)
- **Deployment:** Hugging Face Spaces (Docker)

---

## Running locally

```bash
git clone https://github.com/Csandal17/serenum-app.git
cd serenum-app
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with your own keys:

```
ANTHROPIC_API_KEY=your_key
OPENWEATHER_API_KEY=your_key
TAVILY_API_KEY=your_key
ELEVENLABS_API_KEY=your_key
```

Then run:

```bash
chainlit run app.py
```

Trip forecasts come from Open-Meteo, which needs no key. On Hugging Face, these are set as Space secrets rather than a `.env` file.

### Tests

```bash
pip install pytest
pytest
```

The tests need no API keys and make no real calls to Claude, OpenWeatherMap, Open-Meteo or Tavily.

---

## A note on scope

Sērēnum offers **general, educational information only**. It is not a medical device, it does not diagnose skin conditions, and it is not a substitute for professional dermatological care. Always patch-test new products, and consult a qualified professional for any specific concern.

---

## Credits

- Voice powered by [ElevenLabs](https://elevenlabs.io).
- Weather and air quality data from [OpenWeatherMap](https://openweathermap.org).
- Trip forecasts from [Open-Meteo.com](https://open-meteo.com/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Evidence search by [Tavily](https://tavily.com).

Built as a personal project exploring agentic AI for everyday wellness.