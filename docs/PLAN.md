# Plan projektu zoniq

## Cel

Zbudować wiarygodne narzędzie do analizy planowej dostępności transportowej Warszawy i aglomeracji. Zoniq nie jest nawigacją live: oblicza podróże na podstawie wersjonowanych rozkładów GTFS i grafu pieszego OSM.

## Docelowe doświadczenie produktu

Zoniq odpowiada najpierw na pytanie **„dokąd dotrę w godzinę?”**, a nie
„jak dojadę pomiędzy dwoma punktami?”. Użytkownik wybiera tylko start,
datę, godzinę, okno analizy i limit czasu. Otrzymuje ciągłą mapę zasięgu
Warszawy; kliknięcie celu i szczegóły trasy są funkcją wtórną.

- przesiadki są parametrem wewnętrznym RAPTOR-a (domyślnie maksimum 2),
  a nie głównym elementem sterującym interfejsu;
- pojedynczy scenariusz agreguje starty co minutę w wybranym oknie,
  domyślnie 60 minut;
- kolor mapy pokazuje udział czasu środków transportu w najlepszych
  wariantach, a jasność / krycie pokazują osiągalność i niezawodność;
- wynik przestrzenny jest siatką lub powierzchnią zasięgu, nie chmurą
  przystanków.

## Zakres rozpoczęty

- import i walidacja GTFS ZTM wraz z wersją danych,
- adres lub pinezka jako punkt startowy,
- planowa warstwa osiągalnych przystanków i klikane zapytanie szczegółowe,
- jedna przesiadka na tym samym przystanku jako etap przejściowy silnika.

## Kolejność prac

| Sprint | Rezultat | Kryterium ukończenia |
| --- | --- | --- |
| 1. Dane | importer i walidator GTFS ZTM | powtarzalny import, raport statystyk i wersja danych |
| 2. Routing | graf pieszy + RAPTOR do dwóch przesiadek na obszarze testowym | Kabaty → Centrum zgodne z ręczną weryfikacją |
| 3. Symulacja | start co minutę, siatka wyników i agregacja | GeoJSON z czasem, prawdopodobieństwem i udziałem środków |
| 4. Mapa | powierzchnia zasięgu, legenda wkładu modalnego i kliknięcie punktu | interaktywna mapa bez ponownego pełnego obliczenia |
| 5. Podróże | geokodowanie i szczegóły trasy | segmenty, alternatywy i metryki |

## Zasady jakości

- Każdy wynik przechowuje wersję danych GTFS/OSM i parametry routingu.
- Średni czas jest zawsze prezentowany obok prawdopodobieństwa zmieszczenia się w limicie.
- Dane GTFS różnych operatorów są normalizowane, a identyfikatory zachowują źródłowy feed.
- Najpierw mierzymy poprawność i czas obliczeń, później optymalizujemy.
