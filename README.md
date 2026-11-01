# zoniq

Interaktywna mapa dostępności komunikacyjnej Warszawy i aglomeracji. Użytkownik wybiera punkt startowy, datę oraz godzinę, a aplikacja pokazuje zasięg i szczegóły podróży według rozkładów GTFS.

## Stan

Pierwszy pionowy wycinek jest gotowy: responsywny interfejs scenariusza, kontrakt API FastAPI oraz deterministyczny silnik demonstracyjny. Wyniki są obecnie oznaczone jako demonstracyjne — do czasu podłączenia i zweryfikowania danych GTFS oraz OSM nie reprezentują rzeczywistych rozkładów.

## Uruchomienie

```bash
pnpm install
pnpm dev:web
```

W drugim terminalu:

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Frontend: `http://localhost:3000` · API: `http://localhost:8000/docs`.

## Plan MVP

1. Fundament danych: import i walidacja GTFS ZTM, wersjonowanie źródeł.
2. Silnik: graf pieszy OSM, RAPTOR, symulacja kolejnych minut.
3. Mapa: warstwy MapLibre dla izochron i heatmapy.
4. Adresy: geokodowanie, dokładne zapytania punktowe i szczegóły podróży.
5. Jakość: testy porównawcze, cache, eksport PNG i wdrożenie.

Szczegółowy backlog i decyzje architektoniczne: [docs/PLAN.md](docs/PLAN.md).
