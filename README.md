# zoniq

Interaktywna mapa dostępności komunikacyjnej Warszawy i aglomeracji. Użytkownik wybiera punkt startowy, datę oraz godzinę, a aplikacja pokazuje, dokąd można dotrzeć w zadanym czasie według rozkładów GTFS. Szczegóły pojedynczej trasy są funkcją pomocniczą mapy.

## Stan

Faza 1 jest gotowa lokalnie: użytkownik wskazuje jeden punkt startowy, datę,
godzinę, okno analizy, środki transportu oraz limit 15/30/45/60 minut albo
własną wartość. Aplikacja uśrednia odjazdy co minutę, łączy lokalny rozkład
GTFS ZTM z grafem pieszym OpenStreetMap i pokazuje ciągłą powierzchnię
dostępności. Kliknięcie punktu na mapie daje pomocniczy, szczegółowy wariant
podróży z maksymalnie dwiema przesiadkami.

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

Przygotowanie lokalnego indeksu zapytań:

```bash
python -m app.gtfs prepare ..\..\data\raw\gtfs\ztm\feed.zip --feed-id ztm --database ..\..\data\processed\ztm.sqlite
```

### Graf pieszy OSM

Graf pobiera się jednorazowo i pozostaje lokalnym artefaktem danych:

```bash
python -m app.walking ..\..\data\processed\walking\warsaw.graphml --north 52.38 --south 52.05 --east 21.36 --west 20.76
```

Krawędzie chodnikowe mają wagę czasu marszu; schody liczą się podwójnie.

Po przygotowaniu feedu `POST /api/simulations` uruchamia w tle mapę zasięgu,
a `GET /api/simulations/{id}` zwraca jej status. `POST /api/journeys` jest
funkcją pomocniczą dla klikniętego celu i obsługuje dojścia piesze oraz do
dwóch przesiadek między pobliskimi peronami.

### Sprawdzenie rzeczywistego przebiegu

Po przygotowaniu danych uruchom próbę Kabaty, sobota 17:00:

```bash
cd apps/api
python -m scripts.verify_real_simulation --limit 15 --window 1
```

Skrypt korzysta z prawdziwej bazy GTFS i kafla OSM, dlatego nie jest częścią
szybkich testów jednostkowych.

## Plan MVP

1. Fundament danych: import i walidacja GTFS ZTM, wersjonowanie źródeł.
2. Silnik: graf pieszy OSM, RAPTOR, symulacja kolejnych minut.
3. Mapa: warstwy MapLibre dla izochron i heatmapy.
4. Adresy: geokodowanie, dokładne zapytania punktowe i szczegóły podróży.
5. Jakość: testy porównawcze, cache, eksport PNG i wdrożenie.

Szczegółowy backlog i decyzje architektoniczne: [docs/PLAN.md](docs/PLAN.md).
