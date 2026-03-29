import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf
from scipy.signal import correlate, spectrogram
from scipy.fft import rfft, rfftfreq

# =============================================================================
# KONFIGURACJA SCENY I PARAMETRÓW SYMULACJI
# =============================================================================

# Położenie źródła dźwięku (S1) w przestrzeni [x, y, z]
S1 = np.array([15, 70, -12.0])

# Współrzędne czterech odbiorników (Hydrofonów/Mikrofonów) H1-H4
H_POS = {
    "H1": [0, 150, -4],
    "H2": [50, 0, -4],
    "H3": [300, 50, -4],
    "H4": [50, 100, -4]
}

# Częstotliwość próbkowania [Hz]
fs = 300000


def spectrumA(x, fs):
    """
    Oblicza jednostronne widmo amplitudowe sygnału rzeczywistego.
    """
    N = len(x)
    X = np.abs(rfft(x)) / N
    f = rfftfreq(N, 1.0 / fs)
    return f, X


def generuj_wszystkie_wykresy():
    """
    Główna funkcja przetwarzająca sygnały, obliczająca korelacje wzajemne
    i wizualizująca wyniki analizy TDOA.
    """

    # --- 0. REKONSTRUKCJA SYGNAŁU ŹRÓDŁOWEGO ---
    # Generowanie sygnału referencyjnego (efekt grzebienia - 11 składowych harmonicznych)
    Tp = 0.2  # Czas trwania sygnału [s]
    t_source = np.arange(0, Tp, 1.0 / fs)

    # Definicja częstotliwości tonów (1kHz - 20kHz)
    TF = np.array([1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 18, 19, 20.0]) * 1000.0
    TA = np.array([0.1] * 11)  # Stała amplituda dla każdego tonu

    sig_source_final = np.zeros_like(t_source)
    for i in range(len(TF)):
        sig_source_final += TA[i] * np.sin(2 * np.pi * TF[i] * t_source)

    # Dodanie szumu białego o niskiej energii (AWGN) dla realizmu
    rng = np.random.default_rng(seed=0)
    sig_source_final += rng.normal(0, 0.005, size=sig_source_final.shape)

    # --- 1. WCZYTANIE SYGNAŁÓW ODEBRANYCH ---
    try:
        # Zakładamy, że pliki .wav zostały wygenerowane przez zewnętrzny skrypt symulacyjny
        signals = {n: sf.read(f'{n}.wav')[0] for n in H_POS.keys()}
        t_rx = np.arange(len(signals['H1'])) / fs
    except FileNotFoundError:
        print("BŁĄD: Brak plików .wav! Upewnij się, że dane wejściowe istnieją.")
        return

    # --- 2. WIZUALIZACJA: SYGNAŁ ŹRÓDŁOWY (DOMENA CZASU I CZĘSTOTLIWOŚCI) ---
    fig0, (ax0_t, ax0_f) = plt.subplots(2, 1, figsize=(10, 8))
    ax0_t.plot(t_source, sig_source_final, color='green')
    ax0_t.set_title('Sygnał źródłowy (Referencyjny) - Domena czasu')
    ax0_t.set_xlabel('Czas [s]');
    ax0_t.set_ylabel('Amplituda [V]');
    ax0_t.grid(True)

    f_spec, S = spectrumA(sig_source_final, fs)
    ax0_f.plot(f_spec / 1000.0, 20 * np.log10(S + 1e-12), color='green')
    ax0_f.set_title('Widmo sygnału źródłowego (Struktura grzebieniowa)')
    ax0_f.set_xlabel('Częstotliwość [kHz]');
    ax0_f.set_ylabel('Amplituda [dB]');
    ax0_f.grid(True)
    ax0_f.set_xlim(0, 30)

    # --- 3. WIZUALIZACJA: GEOMETRIA UKŁADU (3D) ---
    fig1 = plt.figure(figsize=(8, 6))
    ax = fig1.add_subplot(111, projection='3d')
    ax.scatter(S1[0], S1[1], S1[2], c='r', s=100, label='Źródło (Cel) S1')
    for n, p in H_POS.items():
        ax.scatter(p[0], p[1], p[2], s=50, label=f'Odbiornik {n}')
    ax.set_title('Rozmieszczenie czujników i źródła w przestrzeni 3D')
    ax.legend();
    ax.set_xlabel('X [m]');
    ax.set_ylabel('Y [m]');
    ax.set_zlabel('Z [m]')

    # --- 4. WIZUALIZACJA: SPEKTROGRAMY (ANALIZA CZASOWO-CZĘSTOTLIWOŚCIOWA) ---
    fig3, axs3 = plt.subplots(2, 2, figsize=(12, 10))
    for i, (name, sig) in enumerate(signals.items()):
        f_s, t_s, Sxx = spectrogram(sig, fs)
        axs3.flat[i].pcolormesh(t_s, f_s / 1000, 10 * np.log10(Sxx + 1e-12), shading='gouraud', cmap='magma')
        axs3.flat[i].set_title(f'Spektrogram sygnału na {name}')
        axs3.flat[i].set_ylim(0, 50)  # Ograniczenie do pasma 50kHz
    fig3.tight_layout()

    # --- 5. ANALIZA TDOA (TIME DIFFERENCE OF ARRIVAL) ---
    # Obliczamy opóźnienia między parami odbiorników wykorzystując korelację wzajemną.
    print("\n" + "=" * 60)
    print(f"{'PARA':<10} | {'TDOA ZMIERZONE (ICC) [s]':<25}")
    print("-" * 60)

    # Wszystkie możliwe kombinacje par dla 4 odbiorników (6 par)
    pary_do_analizy = [('H1', 'H2'), ('H1', 'H3'), ('H1', 'H4'),
                       ('H2', 'H3'), ('H2', 'H4'), ('H3', 'H4')]

    for p1, p2 in pary_do_analizy:
        sig1, sig2 = signals[p1], signals[p2]

        # Obliczenie pełnej korelacji wzajemnej
        corr = correlate(sig1, sig2, mode='full')
        lags = np.arange(-len(sig1) + 1, len(sig1))

        # Znalezienie maksimum (przesunięcie dyskretne)
        idx_max = np.argmax(np.abs(corr))
        m_peak = lags[idx_max]

        # --- INTERPOLACJA PARABOLICZNA (ICC) ---
        # Pozwala na uzyskanie rozdzielczości wyższej niż wynikałoby to z fs
        y1, y2, y3 = corr[idx_max - 1], corr[idx_max], corr[idx_max + 1]
        delta = 0.5 * (y1 - y3) / (y1 - 2 * y2 + y3)  # Wyznaczenie wierzchołka paraboli

        # Finalny czas opóźnienia
        tau = (m_peak + delta) / fs
        print(f"{p1 + '-' + p2:<10} | {tau:.10f} s")

        # --- 6. WYKRESY KORELACJI ---
        fig, (axB1, axB2) = plt.subplots(2, 1, figsize=(10, 8))
        fig.suptitle(f'Analiza korelacji wzajemnej: {p1} vs {p2}')

        axB1.plot(lags, np.abs(corr))
        axB1.set_title(f'Pełna funkcja korelacji')
        axB1.set_xlabel('Przesunięcie (lags)');
        axB1.grid(True)

        # Powiększenie na szczyt korelacji (Zoom)
        rng_zoom = 100
        start, end = max(0, idx_max - rng_zoom), min(len(lags), idx_max + rng_zoom)
        axB2.plot(lags[start:end], np.abs(corr[start:end]), 'o-', label='Próbki dyskretne')
        axB2.axvline(m_peak + delta, color='r', linestyle='--', label=f'Szczyt sub-próbkowy: {tau:.7f}s')
        axB2.set_title(f'Zoom na szczyt korelacji (m={m_peak})')
        axB2.legend();
        axB2.grid(True)
        fig.tight_layout()

    print("=" * 60 + "\n")
    plt.show()


if __name__ == "__main__":
    generuj_wszystkie_wykresy()