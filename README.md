# TDOA Estimation using Cumulative Cross-Correlation with Parabolic Interpolation

### Author: [Marcel Kwiatkowski]
**Project:** Transition Project | **University:** Naval Academy in Gdynia (AMW)

---

## 📑 Table of Contents
1. [About The Project](#-about-the-project)
2. [Repository Structure](#-repository-structure)
3. [Theoretical Background](#-theoretical-background)
4. [Environment Setup](#-environment-setup)
5. [Results Analysis](#-results-analysis)

---

## 🌊 About The Project
This project implements a passive hydroacoustic localization system for an **Unmanned Surface/Aerial Vehicle (USV/UAV) swarm**.

The main objective was to estimate the **Time Difference of Arrival (TDOA)** with sub-sample precision (higher than the sampling period $1/f_s$). By combining **Cumulative Cross-Correlation** with **Parabolic Interpolation (ICC)**, nanosecond-level resolution was achieved at a 300 kHz sampling rate.

---

## 📂 Repository Structure
* 📁 [**scripts/**](scripts/) - Python source code:
    * `SimZopBsp.py` - Signal generator and propagation simulator.
    * `analiza_tdoa.py` - Core calculation engine (Correlation + ICC).
* 📁 [**data/**](data/) - Raw hydroacoustic data in `.wav` format.
* 📁 [**results/**](results/) - Generated visual reports:
    * Signal spectrograms.
    * Correlation plots with sub-sample delta marking.
    * 3D swarm geometry visualization.
* 📄 [**requirements.txt**](requirements.txt) - List of necessary Python libraries.

---

## 🧠 Theoretical Background

### Cumulative Cross-Correlation
For discrete signals $x_1$ and $x_2$, the correlation function is calculated as:
$$R_{x_1x_2}[m] = \sum_{n=0}^{N-1} x_1[n] \cdot x_2[n+m]$$

### Parabolic Interpolation (ICC)
To break the discrete sampling barrier, a sub-sample correction $\delta$ is calculated using three samples around the peak ($y_1, y_2, y_3$):
$$\delta = \frac{0.5(y_1 - y_3)}{y_1 - 2y_2 + y_3}$$
Final TDOA: $TDOA = (m_{peak} + \delta) / f_s$.

---

## 📊 Results Analysis

### Scenario I: Symmetrical Calibration
For a target placed on the symmetry axis of the $H_1-H_2$ pair, the estimation error was approximately **214 nanoseconds**.

| Hydrophone Pair | Measured TDOA (ICC) [s] | Status |
| :--- | :--- | :--- |
| **H1 - H2** | `-0.0000002147` | ✅ Success (Near Zero) |
| **H3 - H4** | `0.1293562645` | ✅ Validated |

## 🖼️ Key Visualizations

### Signal Characteristics
To ensure high correlation precision, a multi-tone signal (comb spectrum) was used. The spectrogram below confirms the stability of the received signal across all channels.

![Spectrogram](results/spektrogramy_h1_h4.png)

### Swarm Geometry
The simulation uses an asymmetric 4-element hydrophone array. This configuration is crucial for avoiding geometric singularities during the 3D positioning phase.

![Geometry 3D](results/geometria_ukladu.png)

### Correlation Visualization
![Correlation H1-H2](results/korelacja_h1_h2_niesymetryczny.png)
*Fig 1: Cross-correlation peak detection with parabolic interpolation.*

---

## 🛠 Environment Setup

1. Clone the repository:
   ```bash
   git clone [https://github.com/](https://github.com/)[marcelkwiatkowski01]/[TDOA].git
