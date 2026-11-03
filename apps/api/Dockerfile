FROM python:3.12-slim

WORKDIR /app

# Produkcyjny kontener wyłącznie wykonuje przygotowane grafy. Pyrosm służy
# tylko do jednorazowego budowania kafli PBF i pozostaje zależnością narzędzi
# deweloperskich, nie runtime API.
RUN pip install --no-cache-dir "fastapi>=0.115,<1" "networkx>=3.4,<4" "uvicorn>=0.34,<1"
RUN pip install --no-cache-dir "scipy>=1.14,<2" "scikit-learn>=1.6,<2"
RUN pip install --no-cache-dir "osmnx>=2.0,<3"

COPY apps/api/app ./app

ENV ZONIQ_GTFS_DATABASE=/data/processed/ztm.sqlite
ENV ZONIQ_SIMULATION_DIRECTORY=/data/simulations

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
