# Program 1: Parallel Fractal Generation Using std::thread

## 1. System Specifications & Experimental Setup
All benchmarks were compiled with `-O3` optimization flag on a 64-bit Linux environment under WSL2.
- **CPU:** Intel(R) Core(TM) i7-14700HX
- **Topology:** 14 Physical Cores (8 Performance-Cores + 12 Efficient-Cores), 28 Logical Threads (vCPUs)
- **Caches:** L1d: 672 KiB, L1i: 448 KiB, L2: 28 MiB, L3: 33 MiB (shared)
- **Sequential Baseline Runtime:** ~222.5 - 224.5 ms (View 1)

---

## 2. Spatial Block Decomposition & The 3-Thread Anomaly (Questions 1 & 2)

### Initial Implementation: Contiguous Row Partitioning
The starter code was initially extended to partition the vertical coordinate space into contiguous horizontal slices:
`numRows = height / numThreads`, `startRow = threadId * numRows`

### Measured Performance (View 1)

| Thread Count (N) | Sequential Time (ms) | Parallel Time (ms) | Measured Speedup | Ideal Speedup | Efficiency (S/N) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1 (Serial)** | 223.68 | 223.68 | **1.00x** | 1.00x | 100.0% |
| **2** | 223.68 | 114.28 | **1.96x** | 2.00x | 98.0% |
| **3** | 222.53 | 138.82 | **1.60x** *(DIP)* | 3.00x | 53.3% |
| **4** | 224.70 | 93.35 | **2.41x** | 4.00x | 60.3% |
| **5** | 222.76 | 93.44 | **2.38x** | 5.00x | 47.6% |
| **6** | 223.18 | 71.19 | **3.14x** | 6.00x | 52.3% |
| **7** | 222.69 | 68.34 | **3.26x** | 7.00x | 46.6% |
| **8** | 223.01 | 58.06 | **3.84x** | 8.00x | 48.0% |
| **10** | 222.44 | 47.91 | **4.64x** | 10.00x | 46.4% |
| **12** | 223.41 | 41.66 | **5.36x** | 12.00x | 44.7% |
| **14** | 224.53 | 36.79 | **6.10x** | 14.00x | 43.6% |

### Analysis: Is Speedup Linear?
**No, speedup is strongly non-linear and suffers severe sub-linear degradation.** 
- At 2 threads, speedup scales near-linearly (1.96x vs 2.00x ideal).
- At 3 threads, an abrupt performance regression occurs: total execution time increases from 114.28 ms to 138.82 ms, dropping the speedup from 1.96x down to 1.60x.
- Beyond 3 threads, scalability resumes but efficiency stagnates around ~45–50%, yielding only 3.84x on 8 threads.

### Hypothesis for the 3-Thread Degradation
In the Mandelbrot set, computing whether a complex number diverges requires iterating `z_{k+1} = z_k^2 + c` up to `maxIterations` (1000 iterations). 
- Pixels far from the boundary diverge in just 1–2 iterations.
- Pixels inside the cardioid and main bulbs require all 1000 iterations.
- In View 1, the computationally dense fractal body is strictly centered vertically (`y ~ 0`).

When partitioning into 3 horizontal blocks:
- **Thread 0 (Top 33%)** and **Thread 2 (Bottom 33%)** receive uniform exterior regions with almost zero computational density.
- **Thread 1 (Middle 33%)** encompasses the entire dense central fractal structure alone.

Because thread execution is synchronized at `join()`, overall wall-clock runtime is bound by `max(T_i)`. Consequently, Thread 1 performs more sequential work than either thread did in the 2-thread configuration (where the dense center was bisected evenly across Thread 0 and Thread 1).

---

## 3. Empirical Verification via CycleTimer (Question 3)

To confirm this hypothesis, individual thread execution times were recorded using `CycleTimer::currentSeconds()` at thread entry and exit.

### Individual Thread Wall-Clock Runtimes (N = 16)

```text
Thread 0  (Rows   0 -  74):   0.76 ms  [Exterior - Low Density]
Thread 15 (Rows 1125 - 1200): 1.15 ms  [Exterior - Low Density]
Thread 1  (Rows  75 - 149):   3.87 ms
Thread 14 (Rows 1050 - 1124): 4.71 ms
Thread 2  (Rows 150 - 224):   5.74 ms
Thread 13 (Rows  975 - 1049): 7.37 ms
Thread 3  (Rows 225 - 299):  18.87 ms
Thread 12 (Rows  900 -  974): 18.50 ms
Thread 4  (Rows 300 - 374):  21.99 ms
Thread 11 (Rows  825 -  899): 25.92 ms
Thread 5  (Rows 375 - 449):  25.81 ms
Thread 10 (Rows  750 -  824): 28.81 ms
Thread 6  (Rows 450 - 524):  32.58 ms
Thread 9  (Rows  675 -  749): 32.35 ms
Thread 7  (Rows 525 - 599):  37.01 ms  [Fractal Core - Extreme Density]
Thread 8  (Rows 600 - 674):  39.34 ms  [Fractal Core - Extreme Density]

Overall Measured Runtime: 35.83 ms (Matches the slowest thread ~37-39 ms)
```
### Key Findings:
1. **50x Workload Disparity:** Thread 8 performed over 50 times more work than Thread 0 (39.34 ms vs. 0.76 ms).
2. **Symmetric Bell Curve:** Workload distribution mirrors the vertical cross-section of the fractal set.
3. **Core Starvation:** Thread 0 completed its work in under 1 millisecond and remained idle for ~35 ms waiting for Thread 7/8. This confirms that spatial block decomposition introduces severe **Load Imbalance**.

---

## 4. Interleaved (Cyclic) Work Decomposition (Question 4)

### Static Round-Robin Policy
To eliminate workload disparity without runtime locking (`mutex`) or inter-thread communication, a cyclic interleaved decomposition was implemented:
- Thread `k` starts at row index `k` and strides by `numThreads`:
  `Row Assignment for Thread k: row = k, k + numThreads, k + 2*numThreads, ...`
- By interleaving row assignments, computationally expensive center rows and inexpensive boundary rows are uniformly distributed across all participating worker threads.

### Benchmark Results (8 Threads):
- **Sequential Baseline:** 224.503 ms
- **Interleaved Thread Runtime:** 32.826 ms
- **Final 8-Thread Speedup:** **6.84x**

### Thread Balance Verification:
Individual thread runtimes under interleaved decomposition converged from a 50x spread down to:
- Fastest Thread: ~31.4 ms
- Slowest Thread: ~34.2 ms
- **Variance: < 3 ms**, indicating near-perfect static load balance.

### Why is 8-Thread Speedup 6.84x and not 8.00x?
1. **Dynamic Frequency Scaling (Intel Turbo Boost / TDP Wall):** Under single-threaded execution, the CPU can sustain maximum single-core boost clock (~5.0 GHz). When all 8 physical cores are fully saturated with intensive floating-point operations, the thermal and power envelope (TDP) throttles all-core frequencies down to ~3.8–4.0 GHz. A frequency reduction from 5.0 GHz to 4.0 GHz mathematically caps theoretical speedup:
   `Max Theoretical Speedup ~ 8 * (4.0 GHz / 5.0 GHz) ~ 6.4x - 6.8x`
2. **Thread Creation & Barrier Latency:** `std::thread` spawn overhead and `join()` synchronization barrier cost.
3. **L1/L2 Cache Pressure:** Interleaved rows are non-contiguous in memory, slightly increasing cache misses compared to bulk sequential scanlines.

---

## 5. Scaling to 16 Threads (Question 5)

### Benchmark Results (16 Threads):
- **Sequential Baseline:** 225.945 ms
- **16-Thread Runtime:** 22.745 ms
- **Final 16-Thread Speedup:** **9.93x**

### Is Performance Noticeably Greater than 8 Threads?
**Yes.** Running with 16 threads reduces execution time from 32.83 ms down to 22.75 ms, achieving an **additional 45% performance improvement** (speedup increases from 6.84x to 9.93x).

### Architectural Reasons:
1. **Hardware Core Count (P-Cores + E-Cores):** The Intel Core i7-14700HX features 8 Performance-Cores (16 threads with Hyper-Threading) and 12 Efficient-Cores. Expanding from 8 to 16 threads allows the OS scheduler to utilize additional dedicated physical silicon execution units rather than multiplexing purely on hyperthreads.
2. **Latency Hiding via Hyper-Threading (SMT):** Even on cores sharing an execution pipeline, Hyper-Threading allows one thread to compute while another thread suffers pipeline stalls, L1 cache misses, or branch recovery.
3. **Diminishing Returns:** The jump from 8 to 16 threads yields a 1.45x boost rather than 2.0x because:
   - Efficient-Cores (E-Cores) have lower IPC (Instructions Per Cycle) and lower clock speeds than P-Cores.
   - Memory bus bandwidth contention increases as 16 threads concurrently write to `output[]`.
