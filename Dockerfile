# Image de production de l'API du simulateur SFD. Le schéma est créé ou
# complété au premier démarrage par l'application elle-même.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Hugging Face Spaces exécute le conteneur avec l'utilisateur 1000.
RUN useradd -m -u 1000 simulateur && chown -R simulateur /app
USER simulateur

ENV PORT=7860 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
