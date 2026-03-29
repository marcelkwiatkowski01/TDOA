"""
Piotr Szymak 2025.10.16 (tłumaczenie Matlab -> Python)
Projekt ZOP-BSP finansowany z NCBR

Symulacja propagacji sygnałów w 4 punktach odbioru w 3D:
- Szerokopasmowe zakłócenia (SNR zależny od długości drogi propagacji)
- Tonowe zakłócenia impulsowe o losowym czasie trwania i występowania
- Pojedyncze rewerberacje od dna i powierzchni wody
Warunki stacjonarne: brak ruchu źródeł i odbiorników (brak Dopplera)
Jednorodny kanał (stała prędkość dźwięku)
Brak uwzględnienia ch-k czułości urządzeń – stałe wzmocnienie toru pomiarowego
"""

import numpy as np
from dataclasses import dataclass, asdict
from scipy.io import savemat
from scipy.signal import stft
import matplotlib.pyplot as plt
from scipy.fft import rfft, rfftfreq
from scipy.signal import stft, windows
from scipy.io.wavfile import write
import soundfile as sf



# ==============================
# Narzędzia pomocnicze
# ==============================

def fractional_delay(x: np.ndarray, delay_s: float, fs: float) -> np.ndarray:
    """Zastosuj ułamkowe opóźnienie (liniowa interpolacja).
    y[n] = x[n - d], gdzie d = delay_s * fs.
    Poza zakresem – dopełnienie zerami."""
    n = np.arange(len(x), dtype=float)
    d = delay_s * fs
    # Interpolujemy wartości x w punktach (n - d)
    y = np.interp(n - d, np.arange(len(x), dtype=float), x, left=0.0, right=0.0)
    return y


def amp_from_tl(distance_m: float, tl_db_per_10m: float) -> float:
    """Współczynnik amplitudowy wynikający ze strat propagacji TL [dB/10 m]."""
    tl_db = (distance_m / 10.0) * tl_db_per_10m
    return 10.0 ** (-tl_db / 20.0)


def mirror_z(point_xyz: np.ndarray, plane_z: float) -> np.ndarray:
    """Odbicie punktu względem płaszczyzny z = plane_z."""
    x, y, z = point_xyz
    z_ref = 2.0 * plane_z - z
    return np.array([x, y, z_ref], dtype=float)


def add_random_tone_bursts(length_n: int, fs: float, rd_params: np.ndarray, level_rms: float) -> np.ndarray:
    """Tonowe zakłócenia impulsowe:
    rd_params = [licz_zakł, maks_czas_trw_s, fmin_kHz, fmax_kHz]
    level_rms – docelowe RMS zakłóceń (skalowanie)."""
    rng = np.random.default_rng()
    count = int(rd_params[0])
    max_dur = float(rd_params[1])
    fmin = float(rd_params[2]) * 1e3
    fmax = float(rd_params[3]) * 1e3

    t = np.arange(length_n) / fs
    burst_sum = np.zeros(length_n, dtype=float)

    for _ in range(count):
        dur = rng.uniform(0.001, max_dur)  # >=1 ms, do maksymalnej długości
        n_dur = max(2, int(dur * fs))
        start = rng.integers(0, max(1, length_n - n_dur))
        f = rng.uniform(fmin, fmax)
        # Okno dla łagodnych zboczy (żeby uniknąć kliknięć)
        win = np.hanning(n_dur)
        phase0 = rng.uniform(0, 2 * np.pi)
        burst = np.sin(2 * np.pi * f * t[:n_dur] + phase0) * win
        burst_sum[start:start + n_dur] += burst

    # Normalizacja do zadanego RMS (jeśli niezerowe)
    cur_rms = np.sqrt(np.mean(burst_sum ** 2)) if np.any(burst_sum) else 0.0
    if cur_rms > 0 and level_rms > 0:
        burst_sum *= (level_rms / cur_rms)
    return burst_sum


def add_awgn_to_snr(signal: np.ndarray, target_snr_db: float, rng=None) -> np.ndarray:
    """Dodaj AWGN, aby osiągnąć docelowy SNR (względem sygnału wejściowego)."""
    if rng is None:
        rng = np.random.default_rng()
    sig_rms = np.sqrt(np.mean(signal ** 2)) + 1e-15
    noise_rms = sig_rms / (10.0 ** (target_snr_db / 20.0))
    noise = rng.normal(0.0, noise_rms, size=signal.shape)
    return signal + noise


# ==============================
# Struktury danych
# ==============================

@dataclass
class HydroStruct:
    # Położenie w przestrzeni źródeł i odbiorników hydroakustycznych
    S1: np.ndarray  # Submarine 1 [x y z]
    H1: np.ndarray  # Hydrophone 1 [x y z]
    H2: np.ndarray
    H3: np.ndarray
    H4: np.ndarray
    # Parametry środowiska
    Bs: float       # stała głębokość dna [m]
    AC: np.ndarray  # współcz. absorpcji od powierzchni wody i dna [-] (surface, bottom)
    Vs: float       # prędkość dźwięku w wodzie [m/s]
    TL: float       # straty propagacji [dB] na 10 m


@dataclass
class SubmStruct:
    # Parametry źródła sygnału
    TF: np.ndarray  # częstotliwości składowych [kHz]
    TA: np.ndarray  # amplitudy składowych [-]
    # Parametry toru pomiarowego
    AM: float       # stałe wzmocnienie [dB]
    Fs: float       # częstotliwość próbkowania [kHz]
    Tp: float       # czas propagacji sygnałów [s]
    # Parametry zakłóceń losowych
    RD: np.ndarray  # [liczba, maks_czas_trw_s, fmin_kHz, fmax_kHz]


# ==============================
# Funkcje główne (odpowiedniki Matlab)
# ==============================

def db2mag(db):
    """Konwersja z dB na współczynnik liniowy."""
    return 10 ** (db / 20.0)

def mag2db(mag):
    """Konwersja ze współczynnika liniowego na dB."""
    mag = np.maximum(np.abs(mag), 1e-20)
    return 20 * np.log10(mag)

def spectrumA(x, fs):
    """Analiza widmowa (amplitudowa) – odpowiednik spectrumA w Matlabie."""
    N = len(x)
    X = np.abs(rfft(x)) / N
    f = rfftfreq(N, 1.0 / fs)
    return f, X

def gen_sign_source(Subm, visualization):
    """
    Generacja sygnału źródłowego z wzmocnieniem toru pomiarowego (SNR)
    oraz losowymi zakłóceniami tonowymi.

    Parametry
    ---------
    Subm : obiekt / dict z polami:
        - Fs [kHz] – częstotliwość próbkowania
        - TF [kHz] – częstotliwości tonów
        - TA [-]   – amplitudy tonów
        - AM [dB]  – wzmocnienie toru pomiarowego
        - Tp [s]   – czas trwania sygnału
        - RD = [licz_zakł., maks_czas_trw., fmin[kHz], fmax[kHz]]
    wizualizacja : int
        1 – pokazuje wykresy, 0 – brak

    Zwraca
    -------
    signS : np.ndarray
        Wygenerowany sygnał źródłowy (z szumem i zakłóceniami).
    """

    fs = Subm.Fs * 1000.0
    f = Subm.TF * 1000.0
    f1 = Subm.RD[2] * 1000.0
    f2 = Subm.RD[3] * 1000.0

    # Budowanie sygnału harmonicznego
    t = np.arange(0, Subm.Tp, 1.0 / fs)
    sign = np.zeros_like(t)
    for i in range(len(f)):
        sign += Subm.TA[i] * np.sin(2 * np.pi * f[i] * t)

    # Dodawanie szumu na podstawie wzmocnienia toru pomiarowego [dB]
    rng = np.random.default_rng(seed=0)
    noise = rng.normal(0, np.std(sign) / db2mag(Subm.AM), size=sign.shape)
    sign2 = sign + noise

    # Dodawanie zakłóceń losowych (tonowych)
    sign3 = sign2.copy()
    n = len(t)
    licz_zakl = int(Subm.RD[0])
    max_dt_s = Subm.RD[1]

    for _ in range(licz_zakl):
        t1 = int(np.round(rng.random() * n))
        dt = int(np.round(rng.random() * max_dt_s / Subm.Tp * n))
        t2 = t1 + dt
        if t2 > n:
            t2 = n
        fd = f1 + rng.random() * (f2 - f1)
        amp = rng.random()
        if t1 < t2:
            sign3[t1:t2] = sign2[t1:t2] + (amp * np.sin(2 * np.pi * fd * t[t1:t2])) / 2.0

    signS = sign3

    # Wizualizacja
    if visualization == 1:
        plt.figure("Wizualizacja sygnału źródłowego", figsize=(10, 8))
        plt.gcf().set_facecolor("w")

        plt.subplot(3, 2, 1)
        plt.plot(t, sign)
        plt.xlabel(r"$\it{t}$ [s]")
        plt.ylabel(r"$\it{s}$ [V]")
        plt.title("Sygnał oryginalny")

        plt.subplot(3, 2, 3)
        plt.plot(t, sign2, "g")
        plt.xlabel(r"$\it{t}$ [s]")
        plt.ylabel(r"$\it{s_n}$ [V]")
        plt.title("Sygnał z szumem szerokopasmowym")

        plt.subplot(3, 2, 5)
        plt.plot(t, sign3, "r")
        plt.xlabel(r"$\it{t}$ [s]")
        plt.ylabel(r"$\it{s_{nd}}$ [V]")
        plt.title("Sygnał z szumem i zakłóceniami tonowymi")

        # Spektra
        plt.subplot(3, 2, 2)
        f_spec, S = spectrumA(sign, fs)
        plt.plot(f_spec / 1000.0, mag2db(S))
        plt.xlabel(r"$\it{f}$ [kHz]")
        plt.ylabel(r"$\it{A}$ [dB]")

        plt.subplot(3, 2, 4)
        f_spec, S2 = spectrumA(sign2, fs)
        plt.plot(f_spec / 1000.0, mag2db(S2), "g")
        plt.xlabel(r"$\it{f}$ [kHz]")
        plt.ylabel(r"$\it{A_n}$ [dB]")

        plt.subplot(3, 2, 6)
        f_spec, S3 = spectrumA(sign3, fs)
        plt.plot(f_spec / 1000.0, mag2db(S3), "r")
        plt.xlabel(r"$\it{f}$ [kHz]")
        plt.ylabel(r"$\it{A_{nd}}$ [dB]")

        plt.tight_layout()
        plt.show()

    return signS

def calc_paths(Hydro):
    """
    Oblicza długości ścieżek propagacji sygnału:
    bezpośredniej (d), od powierzchni (s), od dna (b).

    Parametry
    ----------
    Hydro : dict lub obiekt z polami
        S1 – współrzędne źródła [x, y, z]
        H1–H4 – współrzędne hydrofonów [x, y, z]
        Bs – głębokość dna [m]

    Zwraca
    -------
    propPaths : np.ndarray shape (4, 3)
        Kolumny: [d, s, b] – długości ścieżek dla 4 hydrofonów
    """

    # Pozycje
    S1 = np.array(Hydro.S1, dtype=float)
    H = np.array([
        Hydro.H1,
        Hydro.H2,
        Hydro.H3,
        Hydro.H4
    ], dtype=float)

    # --- Ścieżki bezpośrednie ---
    d = np.zeros(4)
    for i in range(4):
        d[i] = np.sqrt(
            (S1[0] - H[i, 0]) ** 2 +
            (S1[1] - H[i, 1]) ** 2 +
            (S1[2] - H[i, 2]) ** 2
        )

    # --- Ścieżki do i od powierzchni (s) ---
    s = np.zeros(4)
    for i in range(4):
        if S1[2] < H[i, 2]:
            h1 = H[i, 2] - S1[2]
            h2 = abs(H[i, 2])
            a1 = np.sqrt((S1[0] - H[i, 0]) ** 2 + (S1[1] - H[i, 1]) ** 2)
        elif S1[2] > H[i, 2]:
            h1 = S1[2] - H[i, 2]
            h2 = abs(S1[2])
            a1 = np.sqrt((H[i, 0] - S1[0]) ** 2 + (H[i, 1] - S1[1]) ** 2)
        else:  # S1[2] == H[i,2]
            h1 = h2 = a1 = 0.0

        if (h1 + 2 * h2) != 0:
            a2 = h1 * a1 / (h1 + 2 * h2)
        else:
            a2 = 0.0

        b1 = np.sqrt((h1 + h2) ** 2 + ((a1 + a2) ** 2) / 4)
        b2 = np.sqrt(h2 ** 2 + ((a1 - a2) ** 2) / 4)

        if S1[2] == H[i, 2]:
            b1 = np.sqrt((d[i] / 2) ** 2 + (S1[2]) ** 2)
            b2 = b1

        s[i] = b1 + b2

    # --- Ścieżki do i od dna (b) ---
    b = np.zeros(4)
    for i in range(4):
        if S1[2] < H[i, 2]:
            h1 = H[i, 2] - S1[2]
            h2 = S1[2] - Hydro.Bs
            a1 = np.sqrt((S1[0] - H[i, 0]) ** 2 + (S1[1] - H[i, 1]) ** 2)
        elif S1[2] > H[i, 2]:
            h1 = S1[2] - H[i, 2]
            h2 = H[i, 2] - Hydro.Bs
            a1 = np.sqrt((H[i, 0] - S1[0]) ** 2 + (H[i, 1] - S1[1]) ** 2)
        else:
            h1 = h2 = a1 = 0.0

        if (h1 + 2 * h2) != 0:
            a2 = h1 * a1 / (h1 + 2 * h2)
        else:
            a2 = 0.0

        b1 = np.sqrt((h1 + h2) ** 2 + ((a1 + a2) ** 2) / 4)
        b2 = np.sqrt(h2 ** 2 + ((a1 - a2) ** 2) / 4)

        if S1[2] == H[i, 2]:
            b1 = np.sqrt((d[i] / 2) ** 2 + (S1[2] - Hydro.Bs) ** 2)
            b2 = b1

        b[i] = b1 + b2

    # --- Wynik ---
    propPaths = np.column_stack((d, s, b))
    return propPaths


def gen_sign_hydro(signS, Hydro, propPaths, fs, wizualizacja=1):
    """
    Generacja sygnałów odebranych przez hydrofony H1–H4.

    Parametry
    ----------
    signS : ndarray
        Sygnał źródłowy (1D).
    Hydro : dict
        Dane środowiska (Vs, AC, TL, itd.)
    propPaths : ndarray
        Macierz (4x3): [d, s, b] długości ścieżek dla każdego hydrofonu.
    fs : float
        Częstotliwość próbkowania [Hz].
    wizualizacja : int
        0 – brak, 1 – spektrogramy, 2 – przebiegi + widma + spektrogramy.

    Zwraca
    -------
    signH : list[np.ndarray]
        Lista 4 sygnałów odebranych (po rewerberacjach).
    """

    v = Hydro.Vs
    ap = 1 - Hydro.AC[0]  # współczynnik dla powierzchni
    ad = 1 - Hydro.AC[1]  # współczynnik dla dna

    # Obliczanie strat propagacyjnych (pP w dB)
    pP = (propPaths / 10.0) * Hydro.TL

    rng = np.random.default_rng(seed=0)
    signH = []

    # Dodawanie szumów i strat propagacyjnych
    sign = [[None for _ in range(3)] for _ in range(4)]
    #for i in range(4):
    #    for j in range(3):
    #        noise = rng.normal(0, np.std(signS) / db2mag(pP[i, j]), size=len(signS))
    #        sign[i][j] = (signS + noise) / db2mag(pP[i, j])

    for i in range(4):
        for j in range(3):
            # Najpierw tłumienie propagacyjne
            attenuated = signS / db2mag(pP[i, j])
            # Następnie dodanie szumu (po tłumieniu)
            noise = rng.normal(0, np.std(signS) / db2mag(Hydro.TL), size=len(signS))
            sign[i][j] = attenuated + noise



    # Obliczanie opóźnień (w próbkach)
    dt = np.round(propPaths / v * fs).astype(int)

    # Dodawanie opóźnień
    sign2 = [[None for _ in range(3)] for _ in range(4)]
    ws2 = np.zeros((4, 3), dtype=int)
    for i in range(4):
        for j in range(3):
            delay = np.zeros(dt[i, j])
            sign2[i][j] = np.concatenate((delay, sign[i][j]))
            ws2[i, j] = len(sign2[i][j])

    # Normalizacja długości (do najmniejszego sygnału)
    smin2 = np.min(ws2)
    for i in range(4):
        for j in range(3):
            sign2[i][j] = sign2[i][j][:smin2]

    # Dodawanie rewerberacji (odbicia od pow. i dna)
    for i in range(4):
        signH.append(sign2[i][0] + ap * sign2[i][1] + ad * sign2[i][2])

    # Wektor czasu
    t = np.arange(smin2) / fs

    # ================= WIZUALIZACJE =================
    if wizualizacja > 1:
        plt.figure("Wizualizacja sygnałów odebranych H1–H4", figsize=(10, 8))
        plt.gcf().set_facecolor("w")

        # Sygnały bez rewerberacji
        plt.subplot(2, 2, 1)
        for i in range(4):
            plt.plot(t, sign2[i][0], label=f"H{i+1}")
        plt.xlabel(r"$\it{t}$ [s]")
        plt.ylabel(r"$\it{s_{ndl}}$ [V]")
        plt.legend()
        plt.title("Sygnały bezpośrednie + szum")

        # Sygnały po rewerberacjach
        plt.subplot(2, 2, 3)
        for i in range(4):
            plt.plot(t, signH[i], label=f"H{i+1}")
        plt.xlabel(r"$\it{t}$ [s]")
        plt.ylabel(r"$\it{s_{ndlr}}$ [V]")
        plt.legend()
        plt.title("Sygnały z rewerberacjami")

        # Widma
        plt.subplot(2, 2, 2)
        for i in range(4):
            f, S = spectrumA(sign2[i][0], fs)
            plt.plot(f / 1000.0, mag2db(S), label=f"H{i+1}")
        plt.xlabel(r"$\it{f}$ [kHz]")
        plt.ylabel(r"$\it{A_{ndt}}$ [dB]")
        plt.legend()
        plt.title("Widma sygnałów przed rewerberacją")

        plt.subplot(2, 2, 4)
        for i in range(4):
            f, S2 = spectrumA(signH[i], fs)
            plt.plot(f / 1000.0, mag2db(S2), label=f"H{i+1}")
        plt.xlabel(r"$\it{f}$ [kHz]")
        plt.ylabel(r"$\it{A_{ndtr}}$ [dB]")
        plt.legend()
        plt.title("Widma po rewerberacji")

        plt.tight_layout()

    # Spektrogramy STFT
    if wizualizacja >= 1:
        fig, axs = plt.subplots(2, 2, figsize=(10, 8))
        plt.suptitle("Spektrogramy sygnałów odebranych H1–H4", fontsize=12)
        win = windows.kaiser(256, beta=5)
        for i, ax in enumerate(axs.flatten()):
            f, tt, Z = stft(signH[i], fs=fs, nperseg=256, noverlap=220, nfft=512, window=win)
            ax.pcolormesh(tt, f / 1000.0, 20 * np.log10(np.abs(Z) + 1e-12), shading='gouraud')
            ax.set_ylim(0, 50)
            ax.set_title(f"$\\it{{H}}_{{{i+1}}}$")
            ax.set_xlabel(r"$\it{t}$ [s]")
            ax.set_ylabel(r"$\it{f}$ [kHz]")
        plt.tight_layout()

    return signH


def show_hs(Hydro):
    """
    Wizualizacja położenia źródła i odbiorników hydroakustycznych w 3D.

    Parametry
    ----------
    Hydro : dict
        Pola:
        - S1 : [x, y, z] źródło
        - H1–H4 : [x, y, z] hydrofony
    """

    fig = plt.figure("Wizualizacja położenia źródła i odbiorników", figsize=(7, 6))
    fig.patch.set_facecolor("w")
    ax = fig.add_subplot(111, projection='3d')

    # Współrzędne
    S1 = np.array(Hydro.S1, dtype=float)
    H1 = np.array(Hydro.H1, dtype=float)
    H2 = np.array(Hydro.H2, dtype=float)
    H3 = np.array(Hydro.H3, dtype=float)
    H4 = np.array(Hydro.H4, dtype=float)

    # Linie i punkty łączące źródło z hydrofonami
    ax.plot([S1[0], H1[0]], [S1[1], H1[1]], [S1[2], H1[2]], '--o', linewidth=2, label='S1–H1')
    ax.plot([S1[0], H2[0]], [S1[1], H2[1]], [S1[2], H2[2]], '--o', linewidth=2, label='S1–H2')
    ax.plot([S1[0], H3[0]], [S1[1], H3[1]], [S1[2], H3[2]], '--o', linewidth=2, label='S1–H3')
    ax.plot([S1[0], H4[0]], [S1[1], H4[1]], [S1[2], H4[2]], '--o', linewidth=2, label='S1–H4')

    # Opisy punktów
    ax.text(H1[0], H1[1], H1[2], "H₁", ha='left', va='bottom')
    ax.text(H2[0], H2[1], H2[2], "H₂", ha='left', va='bottom')
    ax.text(H3[0], H3[1], H3[2], "H₃", ha='left', va='bottom')
    ax.text(H4[0], H4[1], H4[2], "H₄", ha='left', va='bottom')
    ax.text(S1[0], S1[1], S1[2], "S₁", ha='left', va='bottom')

    # Opisy osi
    ax.set_xlabel(r"$\it{x}$ [m]")
    ax.set_ylabel(r"$\it{y}$ [m]")
    ax.set_zlabel(r"$\it{z}$ [m]")
    ax.legend()
    ax.view_init(elev=20, azim=35)  # widok 3D

    plt.tight_layout()
    plt.show()

# ==============================
# Główny skrypt – odpowiednik pliku .m
# ==============================

if __name__ == "__main__":
    # "clear all" – w Pythonie niepotrzebne

    # Położenie w przestrzeni źródeł i odbiorników hydroakustycznych
    Hydro = HydroStruct(
        S1=np.array([15, 70, -12.0], dtype=float),   # Submarine 1
        H1=np.array([0, 150, -4.0], dtype=float),    # Hydrophone 1
        H2=np.array([50, 0, -4.0], dtype=float),    # Hydrophone 2
        H3=np.array([300, 50, -4.0], dtype=float),  # Hydrophone 3
        H4=np.array([50, 100, -4.0], dtype=float),  # Hydrophone 4
        # Parametry środowiska podwodnego
        Bs=-45.0,                                   # dno [m]
        AC=np.array([0.9, 0.9], dtype=float),       # absorpcja: [powierzchnia, dno]
        Vs=1500.0,                                  # prędkość dźwięku [m/s]
        TL=0.5                                      # straty [dB/10 m]
    )

    # Parametry źródła i toru
    Subm = SubmStruct(
        TF=np.array([1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 18, 19, 20.0], dtype=float),   # [kHz]
        TA=np.array([0.1] * 11, dtype=float),
        AM=20.0,        # [dB]
        Fs=300.0,       # [kHz]
        Tp=0.2,         # [s]
        RD=np.array([10, 0.005, 1, 30], dtype=float)   # [liczba, max_dur_s, fmin_kHz, fmax_kHz]
    )

    # Generowanie sygnału źródłowego
    signS = gen_sign_source(Subm, visualization=0)  # 1: wizualizacja (t,f), 0: brak

    # Obliczanie dróg propagacji
    propPaths = calc_paths(Hydro)



    # Generowanie sygnałów odebranych przez H1–H4
    signH = gen_sign_hydro(
    signS, 
    Hydro,         # przekazanie jako dict
    propPaths,
    fs=int(Subm.Fs * 1000.0),
    wizualizacja=2         # 2: przebiegi + widma + spektrogramy
)



    # Zapis wyników do pliku .mat (jak w Matlabie)
    #savemat(
    #    "sign.mat",
    #    {
    #        "Hydro": {
    #            k: (v if isinstance(v, (int, float, np.ndarray)) else np.array(v))
    #            for k, v in asdict(Hydro).items()
    #        },
    #        "Subm": {
    #            k: (v if isinstance(v, (int, float, np.ndarray)) else np.array(v))
    #            for k, v in asdict(Subm).items()
    #        },
    #        "signS": signS,
    #        "signH": signH
    #    },
    #    do_compression=True
    #)

    # Zapis sygnałów z każdego hydrofonu do osobnych plików WAV
    fs_out = int(Subm.Fs*1000)
    for i, sig in enumerate(signH, start=1):
        fname = f"H{i}.wav"
        sf.write(fname, sig.astype(np.float32), fs_out)
        print(f"Zapisano {fname} ({len(sig)} próbek, {fs_out} Hz)")

    
    # Wizualizacja położenia źródła i odbiorników
    #show_hs(Hydro)

    # Pokaż wszystkie rysunki
    plt.show()

