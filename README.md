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

**An AI skincare advisor that translates live weather into personalised skin guidance.**

🔗 **[Try it live](https://huggingface.co/spaces/Csandal17/serenum)**

Tell Sērēnum where you are, and it reads the current UV index, humidity, temperature, and air quality for your location, then turns that into a short, practical skin brief — what to protect against today, which ingredients to lean on, and which to hold off on. You can also ask it skincare myth and science questions, and it will answer with cited, evidence-backed sources.

---

## The brief, and the spin

Sērēnum started from a simple prompt: build a *Smart Weather Assistant* — an AI agent that delivers real-time conditions and personalised suggestions.

Most takes on that brief suggest activities ("good day for a run"). Mine went somewhere I actually care about. Weather doesn't just decide whether to bring an umbrella — it quietly dictates what your skin needs. High UV with cloud cover still burns. Low humidity pulls moisture out of your skin. Poor air quality stresses your barrier. Sērēnum turns the same live weather data into skincare that responds to the day in front of you.

It works off **real-time** data, not forecasting — the brief reflects conditions right now, which is exactly when you're deciding what to put on your face.

---

## What it does

- **Skin brief** — a personalised read on today's UV, humidity, and air quality, with practical SPF, hydration, and barrier advice.
- **Travel mode** — adjust your routine for somewhere you're heading next.
- **Routine builder** — an AM/PM routine tuned to your local climate.
- **Myth buster** — ask a skincare claim ("does drinking water hydrate your skin?") and get an evidence-backed answer with cited sources, not folklore.
- **Listen** — tap to hear a short spoken version of any brief, narrated in a calm voice. Built for the getting-ready-in-the-morning moment, when reading a screen isn't always practical.

---

## Why weather?

Three live signals do most of the work:

- **UV index** drives the single most important decision of the day — sun protection. It stays high under cloud, which is why a brief beats a glance out the window.
- **Humidity and temperature** shape hydration. Dry, cold air calls for richer occlusives; warm, humid air calls for lighter layers.
- **Air quality (AQI / PM2.5)** affects the skin barrier. Pollution is an oxidative stressor, which is where antioxidants like vitamin C earn their place.

Sērēnum combines all three into one coherent recommendation rather than three disconnected facts.

---

## Architecture

```
        User  (Chainlit chat UI, custom-branded)
          │
          ▼
   LangChain agent  ◄───  Claude (Anthropic API) — reasoning + tool choice
          │
          ├─ weather_tool ─────────►  OpenWeatherMap  (temp, humidity, conditions)
          ├─ air_quality_tool ─────►  OpenWeatherMap  (AQI, PM2.5)
          ├─ uv_tool ──────────────►  OpenWeatherMap  (UV index)
          └─ evidence_search_tool ─►  Tavily          (sources for myth-busting)
          │
          ▼
     Skin brief (text)
          │
          └─ "Listen" ─►  spoken_summary (Claude) ─►  ElevenLabs TTS ─►  audio
```

The agent uses a tool-calling loop: Claude decides which tools to call, runs them, and synthesises the results into the brief. The Listen feature is deliberately a two-step pipeline — a formatted brief (with tables and source links) doesn't read well aloud, so a short *speech-friendly* summary is generated first, then voiced.

---

## Tech stack

- **Agent framework:** LangChain (tool-calling loop with `.bind_tools()`)
- **Reasoning:** Anthropic API (Claude)
- **UI:** Chainlit (custom theme, branding, and `Listen` action)
- **Weather data:** OpenWeatherMap (current weather, UV, air quality)
- **Evidence search:** Tavily
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

On Hugging Face, these are set as Space secrets rather than a `.env` file.

---

## A note on scope

Sērēnum offers **general, educational guidance only**. It is not a medical device, it does not diagnose skin conditions, and it is not a substitute for professional dermatological care. Always patch-test new products, and consult a qualified professional for any specific concern.

---

## Credits

- Voice powered by [ElevenLabs](https://elevenlabs.io).
- Weather and air quality data from [OpenWeatherMap](https://openweathermap.org).
- Evidence search by [Tavily](https://tavily.com).

Built as a personal project exploring agentic AI for everyday wellness.