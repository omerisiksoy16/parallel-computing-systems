# Program 1: Parallel Fractal Generation Using std::thread

## 1. System Specifications & Experimental Setup
All benchmarks were compiled with the `-O3` optimization flag on a 64-bit Linux environment under WSL2.
* **CPU:** Intel Core i7-14700HX
* **Topology:** 20 Physical Cores (8 Performance-Cores + 12 Efficient-Cores), 28 Logical Threads (vCPUs)
* **Caches:** L1d: 672 KiB, L1i: 448 KiB, L2: 28 MiB, L3: 33 MiB (shared)
* **Sequential Baseline Runtime:** ~222.5 – 224.5 ms (View 1)

---

## 2. Spatial Block Decomposition & The 3-Thread Anomaly (Questions 1 & 2)

### Initial Implementation: Contiguous Row Partitioning
The starter code was extended to partition the vertical coordinate space into contiguous horizontal slices:
$$numRows = \frac{height}{numThreads}, \quad startRow = threadId \times numRows$$

### Measured Performance (View 1)

| Thread Count ($N$) | Sequential Time (ms) | Parallel Time (ms) | Measured Speedup | Ideal Speedup | Parallel Efficiency ($S/N$) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1 (Serial)** | 223.68 ms | 223.68 ms | 1.00x | 1.00x | 100.0% |
| **2** | 223.68 ms | 114.28 ms | 1.96x | 2.00x | 98.0% |
| **3** | 222.53 ms | 138.82 ms | **1.60x (DIP)** | 3.00x | 53.3% |
| **4** | 224.70 ms | 93.35 ms | 2.41x | 4.00x | 60.3% |
| **5** | 222.76 ms | 93.44 ms | 2.38x | 5.00x | 47.6% |
| **6** | 223.18 ms | 71.19 ms | 3.14x | 6.00x | 52.3% |
| **7** | 222.69 ms | 68.34 ms | 3.26x | 7.00x | 46.6% |
| **8** | 223.01 ms | 58.06 ms | 3.84x | 8.00x | 48.0% |
| **10** | 222.44 ms | 47.91 ms | 4.64x | 10.00x | 46.4% |
| **12** | 223.41 ms | 41.66 ms | 5.36x | 12.00x | 44.7% |
| **14** | 224.53 ms | 36.79 ms | 6.10x | 14.00x | 43.6% |

### Analysis: Is Speedup Linear?
No, speedup is strongly non-linear and suffers severe sub-linear degradation:
* At **2 threads**, speedup scales near-linearly ($1.96\times$ vs $2.00\times$ ideal).
* At **3 threads**, an abrupt performance regression occurs: execution time increases from 114.28 ms to 138.82 ms, dropping speedup from $1.96\times$ down to $1.60\times$.
* Beyond 3 threads, scalability resumes, but efficiency stagnates around ~45–50%, yielding only $3.84\times$ on 8 threads.

### Hypothesis for the 3-Thread Degradation
In the Mandelbrot set, computing whether a complex number diverges requires evaluating the recurrence relation $z_{k+1} = z_k^2 + c$ up to `maxIterations` (1000 iterations):
* Pixels far from the boundary diverge in just 1–2 iterations.
* Pixels inside the cardioid and main bulbs require all 1000 iterations.
* In View 1, the computationally dense fractal body is strictly centered vertically ($y \approx 0$).

When partitioning the workload into 3 contiguous horizontal blocks:
* **Thread 0 (Top 33%)** and **Thread 2 (Bottom 33%)** receive uniform exterior regions with near-zero computational density.
* **Thread 1 (Middle 33%)** encompasses the entire dense central fractal structure alone.

Because thread execution is synchronized at `join()`, overall wall-clock runtime is bounded by the slowest thread:
$$T_{\text{total}} = \max(T_0, T_1, T_2)$$

Consequently, Thread 1 performs more sequential work than either thread did in the 2-thread configuration (where the dense center was bisected evenly across Thread 0 and Thread 1).

---

## 3. Empirical Verification via CycleTimer (Question 3)

To confirm this hypothesis, individual thread execution times were recorded using `CycleTimer::currentSeconds()` at thread entry and exit.

### Individual Thread Wall-Clock Runtimes ($N = 16$, Contiguous Partitioning)
* **Thread 0**  (Rows   0 –  74):   **0.76 ms**  [Exterior – Low Density]
* **Thread 15** (Rows 1125 – 1200): **1.15 ms**  [Exterior – Low Density]
* **Thread 1**  (Rows  75 – 149):   3.87 ms
* **Thread 14** (Rows 1050 – 1124): 4.71 ms
* **Thread 2**  (Rows 150 – 224):   5.74 ms
* **Thread 13** (Rows  975 – 1049): 7.37 ms
* **Thread 3**  (Rows 225 – 299):  18.87 ms
* **Thread 12** (Rows  900 –  974): 18.50 ms
* **Thread 4**  (Rows 300 – 374):  21.99 ms
* **Thread 11** (Rows  825 –  899): 25.92 ms
* **Thread 5**  (Rows 375 – 449):  25.81 ms
* **Thread 10** (Rows  750 –  824): 28.81 ms
* **Thread 6**  (Rows 450 – 524):  32.58 ms
* **Thread 9**  (Rows  675 –  749): 32.35 ms
* **Thread 7**  (Rows 525 – 599):  **37.01 ms**  [Fractal Core – Extreme Density]
* **Thread 8**  (Rows 600 – 674):  **39.34 ms**  [Fractal Core – Extreme Density]

**Overall Measured Wall-Clock Runtime:** **39.85 ms** (governed by $\max(T_i) = 39.34\text{ ms}$ plus thread creation and barrier join overhead).

### Key Findings
1. **$50\times$ Workload Disparity:** Thread 8 performed over 50 times more work than Thread 0 (39.34 ms vs. 0.76 ms).
2. **Symmetric Bell Curve:** Workload distribution mirrors the vertical cross-section of the fractal set.
3. **Core Starvation:** Thread 0 completed its work in under 1 millisecond and remained idle for ~38 ms waiting for Threads 7 and 8. This empirically proves that spatial block decomposition introduces severe load imbalance.

---

## 4. Interleaved (Cyclic) Work Decomposition (Question 4)

### Static Round-Robin Policy
To eliminate workload disparity without runtime mutex locking or inter-thread communication, a cyclic interleaved decomposition was implemented:
$$row = k, \; k + numThreads, \; k + 2 \times numThreads, \; \dots$$

By interleaving row assignments, computationally expensive center scanlines and inexpensive exterior scanlines are distributed uniformly across all participating threads.

### Benchmark Results (8 Threads):
* **Sequential Baseline:** 224.503 ms
* **Interleaved Thread Runtime:** 32.826 ms
* **Final 8-Thread Speedup:** **$6.84\times$**

### Thread Balance Verification
Under cyclic decomposition, thread runtimes converged from a $50\times$ spread down to near-uniform execution:
* **Fastest Thread:** ~31.4 ms
* **Slowest Thread:** ~34.2 ms
* **Variance:** $< 3\text{ ms}$, confirming balanced workload distribution.

### Factors Limiting Theoretical $8.00\times$ Speedup
1. **Dynamic Frequency Scaling & Thermal Envelope (Analytical Model):** Under single-threaded execution, the CPU can sustain higher single-core Turbo Boost frequencies (~5.0 GHz). When all physical cores are concurrently saturated with intensive arithmetic, the processor's thermal and power limits (TDP) throttle all-core frequencies down to approximately ~3.8–4.0 GHz. A frequency reduction from 5.0 GHz to 4.0 GHz mathematically constrains maximum achievable scaling:
   $$\text{Max Scaling Factor} \approx 8 \times \left(\frac{4.0\text{ GHz}}{5.0\text{ GHz}}\right) \approx 6.4\times \dots 6.8\times$$
2. **Thread Management Overhead:** Latency incurred during `std::thread` construction and final `join()` synchronization.
3. **L1/L2 Cache Spatial Locality:** Interleaved rows stride across memory non-contiguously, slightly increasing cache miss rates relative to contiguous block chunks.

---

## 5. Scaling to 16 Threads (Question 5)

### Benchmark Results (16 Threads):
* **Sequential Baseline:** 225.945 ms
* **16-Thread Runtime:** 22.745 ms
* **Final 16-Thread Speedup:** **$9.93\times$**

### Analysis of Scaling Beyond 8 Threads
Running with 16 threads reduces execution time from 32.83 ms down to 22.75 ms, achieving an additional $45\%$ performance gain ($6.84\times \rightarrow 9.93\times$).

### Architectural Factors
1. **Hybrid Core Architecture (P-Cores + E-Cores):** The Intel Core i7-14700HX contains 8 Performance-Cores (16 threads with Hyper-Threading) and 12 Efficient-Cores. Scaling beyond 8 threads engages additional physical execution pipelines.
2. **Latency Hiding via SMT (Hyper-Threading):** Dual hardware threads per P-core allow the pipeline to switch execution contexts when one thread stalls on memory loads or branch recovery.
3. **Sub-Linear 16-Thread Efficiency ($9.93\times$ vs $16\times$):**
   * **Core Heterogeneity:** E-Cores operate at lower clock frequencies and lower IPC than P-Cores.
   * **Memory Bus Contention:** Increased concurrent writes to the shared output frame buffer increase L3 cache traffic and bus utilization.
