# Wyznaczanie TDOA przy użyciu skumulowanej korelacji wzajemnej z interpolacją paraboliczną

### Autor: [Marcel Kwiatkowski]
**Kierunek:** [Automatyka i Robotyka] | **Uczelnia:** Akademia Marynarki Wojennej w Gdyni
**Projekt Przejściowy - Laboratorium Hydroakustyki**

---

## 📑 Spis treści
1. [O Projekcie](#-o-projekcie)
2. [Struktura Repozytorium](#-struktura-repozytorium)
3. [Podstawy Teoretyczne](#-podstawy-teoretyczne)
4. [Konfiguracja Środowiska](#-konfiguracja-środowiska)
5. [Analiza Wyników](#-analiza-wyników)
6. [Bibliografia](#-bibliografia)

---

## 🌊 O Projekcie
Projekt dotyczy implementacji pasywnego systemu lokalizacji jednostek podwodnych przez mobilny **rój Bezzałogowych Systemów Powietrznych/Nawodnych (R-BSP)**. 

Głównym wyzwaniem była estymacja różnicy czasu nadejścia sygnału (**TDOA**) z precyzją wyższą niż wynika to z częstotliwości próbkowania ($f_s = 300\text{ kHz}$). Zastosowanie **skumulowanej korelacji wzajemnej** w połączeniu z **interpolacją paraboliczną (ICC)** pozwoliło na uzyskanie rozdzielczości sub-samplowej na poziomie nanosekundowym.

---

## 📂 Struktura Repozytorium
Kliknij w poniższe linki, aby przejść do odpowiednich sekcji projektu:

* 📁 [**scripts/**](scripts/) - Zawiera kody źródłowe w języku Python:
    * `SimZopBsp.py` - Generator sygnałów i symulator propagacji.
    * `analiza_tdoa.py` - Główny silnik obliczeniowy korelacji i ICC.
* 📁 [**data/**](data/) - Surowe dane hydroakustyczne w formacie `.wav` dla różnych scenariuszy.
* 📁 [**results/**](results/) - Wygenerowane raporty graficzne:
    * Spektrogramy sygnałów.
    * Wykresy korelacji z naniesioną deltą sub-samplową.
    * Wizualizacja geometrii roju 3D.
* 📄 [**requirements.txt**](requirements.txt) - Lista bibliotek niezbędnych do uruchomienia projektu.

---

## 🧠 Podstawy Teoretyczne

### Skumulowana Korelacja Wzajemna
Dla sygnałów dyskretnych $x_1$ i $x_2$ wyznaczamy funkcję korelacji:
$$R_{x_1x_2}[m] = \sum_{n=0}^{N-1} x_1[n] \cdot x_2[n+m]$$

### Interpolacja Paraboliczna (ICC)
Aby uzyskać precyzję sub-samplową, wyznaczamy poprawkę $\delta$ na podstawie trzech próbek wokół maksimum ($y_1, y_2, y_3$):
$$\delta = \frac{0.5(y_1 - y_3)}{y_1 - 2y_2 + y_3}$$
Ostateczny wynik TDOA: $TDOA = (m_{peak} + \delta) / f_s$.

---

## 📊 Analiza Wyników

### Scenariusz I: Kalibracja Symetryczna
Dla celu umieszczonego w osi symetrii pary $H_1-H_2$ uzyskano błąd estymacji rzędu **214 nanosekund**, co stanowi 0.06 okresu próbkowania.

| Para Hydrofonów | TDOA Zmierzone (ICC) [s] | Stan |
| :--- | :--- | :--- |
| **H1 - H2** | `-0.0000002147` | ✅ Sukces (Idealne zero) |
| **H3 - H4** | `0.1605173079` | ✅ Zgodne z geometrią |

### Wizualizacja korelacji (Przykład)
![Korelacja H1-H2](results/korelacja_h1_h2_niesymetryczny.png)
*Rys. 1: Wyznaczenie szczytu korelacji z uwzględnieniem interpolacji parabolicznej.*

---

## 🛠 Konfiguracja Środowiska

1. Sklonuj repozytorium:
   ```bash
   git clone [https://github.com/](https://github.com/)[TWOJ-LOGIN]/[NAZWA-REPO].git
