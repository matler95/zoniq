# zoniq

Interaktywna mapa dostępności komunikacyjnej Warszawy i aglomeracji. Użytkownik wybiera punkt startowy, datę oraz godzinę, a aplikacja pokazuje zasięg i szczegóły podróży według rozkładów GTFS.

## Stan

Pierwszy pionowy wycinek jest gotowy: responsywny interfejs scenariusza, kontrakt API FastAPI oraz deterministyczny silnik demonstracyjny. Fundament danych zawiera też walidator GTFS z raportem wersji źródła i zakresu kalendarza. Wyniki są nadal oznaczone jako demonstracyjne — do czasu importu i zweryfikowania danych GTFS oraz OSM nie reprezentują rzeczywistych rozkładów.

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

### Walidacja GTFS

Po pobraniu feedu uruchom walidację przed przetwarzaniem danych:

```bash
cd apps/api
python -m app.gtfs inspect ..\..\data\raw\gtfs\ztm\feed.zip --feed-id ztm
```

Polecenie weryfikuje obowiązkowe tabele i kolumny GTFS, liczy rekordy,
zapisuje hash SHA-256 oraz zakres kalendarza do `data/processed/metadata/`.

Przygotowanie lokalnego indeksu zapytań dla pierwszych tras bez przesiadek:

```bash
python -m app.gtfs prepare ..\..\data\raw\gtfs\ztm\feed.zip --feed-id ztm --database ..\..\data\processed\ztm.sqlite
```

Po przygotowaniu feedu `POST /api/journeys` zwraca pierwsze planowe połączenia bez przesiadki dla pary współrzędnych. API wyraźnie oznacza zakres tego etapu; algorytm wieloprzejściowy jest kolejnym krokiem silnika.

## Plan MVP

1. Fundament danych: import i walidacja GTFS ZTM, wersjonowanie źródeł.
2. Silnik: graf pieszy OSM, RAPTOR, symulacja kolejnych minut.
3. Mapa: warstwy MapLibre dla izochron i heatmapy.
4. Adresy: geokodowanie, dokładne zapytania punktowe i szczegóły podróży.
5. Jakość: testy porównawcze, cache, eksport PNG i wdrożenie.

Szczegółowy backlog i decyzje architektoniczne: [docs/PLAN.md](docs/PLAN.md).
