# Plan projektu zoniq

## Cel

Zbudować wiarygodne narzędzie do analizy planowej dostępności transportowej Warszawy i aglomeracji. Zoniq nie jest nawigacją live: oblicza podróże na podstawie wersjonowanych rozkładów GTFS i grafu pieszego OSM.

## Zakres rozpoczęty

- formularz scenariusza (punkt, data, godzina, limit, przesiadki, środki transportu),
- kontrakt `POST /api/simulations`,
- status danych i wynik punktowy,
- demonstracyjny wynik, jawnie oznaczony jako nieprodukcyjny.

## Kolejność prac

| Sprint | Rezultat | Kryterium ukończenia |
| --- | --- | --- |
| 1. Dane | importer i walidator GTFS ZTM | powtarzalny import, raport statystyk i wersja danych |
| 2. Routing | graf pieszy + RAPTOR na obszarze testowym | Kabaty → Centrum zgodne z ręczną weryfikacją |
| 3. Symulacja | siatka wyników i agregacja okna minutowego | GeoJSON z czasem i prawdopodobieństwem |
| 4. Mapa | MapLibre, legenda i kliknięcie punktu | interaktywna mapa bez ponownego pełnego obliczenia |
| 5. Podróże | geokodowanie i szczegóły trasy | segmenty, alternatywy i metryki |

## Zasady jakości

- Każdy wynik przechowuje wersję danych GTFS/OSM i parametry routingu.
- Średni czas jest zawsze prezentowany obok prawdopodobieństwa zmieszczenia się w limicie.
- Dane GTFS różnych operatorów są normalizowane, a identyfikatory zachowują źródłowy feed.
- Najpierw mierzymy poprawność i czas obliczeń, później optymalizujemy.
