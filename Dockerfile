# Sērēnum — Chainlit app for Hugging Face Spaces (Docker SDK)
FROM python:3.13-slim

# Create a non-root user (Hugging Face Spaces requirement)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Install dependencies first (better build caching)
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the app (app.py, agent.py, tools.py, public/, .chainlit/)
COPY --chown=user . /app

# Chainlit must listen on 0.0.0.0:7860 for Hugging Face Spaces
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "7860"]
