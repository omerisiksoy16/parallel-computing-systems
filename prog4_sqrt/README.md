# Program 4: Parallel Sqrt via ISPC Task & Vector Execution

## Overview
This benchmark evaluates the arithmetic performance and scaling characteristics of an iterative Newton-Raphson square root algorithm ($1/\sqrt{x}$) implemented using:
1. Scalar sequential C++ execution (`sqrtSerial`).
2. Single-core SIMD vectorization via the Intel SPMD Program Compiler (`sqrt_ispc`, AVX2 8-wide).
3. Multi-core task parallelism combined with SIMD vectorization (`sqrt_ispc_task`).

All benchmarks were executed on an **Intel Core i7-14700HX** (20 physical cores: 8 P-cores + 12 E-cores, 28 hardware threads) running Ubuntu 22.04 LTS via WSL2. The compiler target is AVX2 (`--target=avx2`), producing 8-wide 32-bit floating-point SIMD vector instructions.

---

## 1. Baseline Performance & Scaling Analysis

### Measured Execution Times (Random Input: $[0.001, 2.999]$)
* **Sequential Baseline ($T_{\text{serial}}$):** `501.097 ms`
* **ISPC Single-Threaded ($T_{\text{ispc}}$):** `135.868 ms`
* **ISPC Multi-Tasked ($T_{\text{task}}$):** `10.984 ms`

### Speedup Decomposition
1. **SIMD Parallelization Speedup:**
   $$\text{Speedup}_{\text{SIMD}} = \frac{T_{\text{serial}}}{T_{\text{ispc}}} = \frac{501.097\text{ ms}}{135.868\text{ ms}} = \mathbf{3.69\times}$$
   On an 8-wide SIMD machine, theoretical peak speedup is $8.0\times$. The observed $3.69\times$ is bounded by control-flow divergence: random input values require varying numbers of Newton-Raphson iterations to converge. A vector lane must remain active until the slowest lane in its 8-element gang finishes, leaving faster lanes idle via masking.

2. **Multi-Core Parallelization Speedup:**
   $$\text{Speedup}_{\text{multi-core}} = \frac{T_{\text{ispc}}}{T_{\text{task}}} = \frac{135.868\text{ ms}}{10.984\text{ ms}} = \mathbf{12.37\times}$$
   Distributing iterations across the ISPC task pool schedules chunks across physical cores, yielding a $12.37\times$ scaling factor.

3. **Aggregate Speedup:**
   $$\text{Speedup}_{\text{aggregate}} = \frac{T_{\text{serial}}}{T_{\text{task}}} = \frac{501.097\text{ ms}}{10.984\text{ ms}} = \mathbf{45.62\times} \quad (3.69\times \times 12.37\times)$$

---

## 2. Best-Case Input: Maximizing Speedup

To maximize relative speedup over the scalar baseline, input values must satisfy two architectural conditions:
1. **Eliminate Vector Lane Divergence:** All 8 lanes in an AVX2 vector register must perform identical iteration counts ($100\%$ vector lane utilization).
2. **Maximize Arithmetic Intensity:** Heavy iteration counts amortize loop setup, pointer arithmetic, and initial load latency.

The algorithm uses initial guess $x_0 = 1.0\text{f}$. Inputs close to $3.0\text{f}$ induce maximum error $\vert{}x_0 \cdot x_0 \cdot x - 1.0\text{f}\vert{}$, requiring the maximum number of iterations before convergence.

### Benchmark (`values[i] = 2.998f`)
* **Sequential Baseline ($T_{\text{serial}}$):** `808.205 ms`
* **ISPC Single-Threaded ($T_{\text{ispc}}$):** `194.603 ms` ($\mathbf{4.15\times}$ speedup)
* **ISPC Multi-Tasked ($T_{\text{task}}$):** `16.538 ms` ($\mathbf{48.87\times}$ speedup)

### Architectural Analysis
* **SIMD Speedup Improvement:** Increased from $3.69\times$ to **$4.15\times$**. Every vector lane runs for the exact same duration. No lane is masked off or idles prematurely.
* **Multi-Core Scaling:**
  $$\text{Speedup}_{\text{multi-core}} = \frac{194.603\text{ ms}}{16.538\text{ ms}} = \mathbf{11.77\times}$$
  Multi-core scaling remains approximately invariant ($\sim 12\times$). Multi-core task distribution partitions the array uniformly across worker threads; it does not depend on data-level vector lane convergence.

---

## 3. Worst-Case Input: Minimizing Speedup (SIMD Divergence Pathologies)

To minimize SIMD speedup, the input pattern must maximize control-flow divergence within each 8-wide AVX2 vector gang.

### Tested Configurations

#### A. Zero-Work Convergence: `values[i] = 1.0f`
* **Sequential Baseline:** `8.057 ms`
* **ISPC Single-Threaded:** `6.655 ms` ($\mathbf{1.21\times}$)
* **ISPC Multi-Tasked:** `2.484 ms` ($\mathbf{3.24\times}$)
* **Analysis:** With initial guess $x_0 = 1.0\text{f}$, initial error is zero. The loop terminates on iteration 0 across all lanes. Memory access and task runtime dispatch dominate execution time, severely limiting parallel scaling (Amdahl's Law).

#### B. Pathological Vector Divergence: `if (i % 8 == 0) values[i] = 2.999f; else values[i] = 1.0f;`
* **Sequential Baseline ($T_{\text{serial}}$):** `133.242 ms`
* **ISPC Single-Threaded ($T_{\text{ispc}}$):** `215.216 ms` ($\mathbf{0.62\times}$ — **38% Slowdown**)
* **ISPC Multi-Tasked ($T_{\text{task}}$):** `18.067 ms` ($\mathbf{7.37\times}$)

### Root-Cause Efficiency Loss
1. **Scalar Behavior:** For 7 out of every 8 array elements (`values[i] = 1.0f`), the scalar loop terminates immediately after 0 arithmetic iterations. Only 1 out of 8 elements executes the full Newton-Raphson loop. Total serial work is $\approx \frac{1}{8} N \times \text{iterations}$.
2. **SIMD AVX2 Behavior:** An 8-wide vector packs indices $[8k \dots 8k+7]$. Lane 0 requires full iterations, while lanes 1–7 terminate immediately. Under lockstep SIMD execution:
   * The vector instruction pointer cannot advance past the loop until **all** active lanes satisfy the exit condition.
   * Lanes 1–7 are masked off (`mask = 0`), sitting idle and consuming execution cycles.
   * **Active Vector Lane Utilization drops to $\frac{1}{8} = 12.5\%$**.
3. **True Slowdown ($0.62\times$):** Because AVX2 executes the full loop duration for every vector chunk while incurring mask generation, branch testing (`vptest`), and pack/unpack overhead, single-core ISPC is slower than the unvectorized scalar loop.
4. **Decoupled Multi-Core Scaling:** Despite the SIMD breakdown, multi-core task scheduling maintains its expected efficiency:
   $$\frac{215.216\text{ ms}}{18.067\text{ ms}} = \mathbf{11.91\times}$$
   Aggregate speedup drops to $7.37\times$ entirely due to the collapsed SIMD factor ($0.62 \times 11.91 \approx 7.37$).

---

## 4. Summary Benchmark Matrix

| Input Configuration | $T_{\text{serial}}$ | $T_{\text{ispc}}$ | SIMD Speedup | $T_{\text{task}}$ | Multi-Core Scaling | Aggregate Speedup | Primary Limiting Factor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Uniform Max (`2.998f`)** | $808.21\text{ ms}$ | $194.60\text{ ms}$ | **$4.15\times$** | $16.54\text{ ms}$ | $11.77\times$ | **$48.87\times$** | Hardware ALUs / FMA saturation |
| **Uniform Min (`0.001f`)** | $394.51\text{ ms}$ | $99.40\text{ ms}$ | **$3.97\times$** | $9.82\text{ ms}$ | $10.12\times$ | **$40.18\times$** | Lower iteration count |
| **Random Baseline** | $501.10\text{ ms}$ | $135.87\text{ ms}$ | **$3.69\times$** | $10.98\text{ ms}$ | $12.37\times$ | **$45.62\times$** | Moderate SIMD lane divergence |
| **Partial Divergence (`i%8==0 ? 2.998 : 0.001`)** | $452.61\text{ ms}$ | $195.12\text{ ms}$ | **$2.32\times$** | $16.97\text{ ms}$ | $11.50\times$ | **$26.68\times$** | Significant lane masking |
| **Zero-Work (`1.0f`)** | $8.06\text{ ms}$ | $6.66\text{ ms}$ | **$1.21\times$** | $2.48\text{ ms}$ | $2.68\times$ | **$3.24\times$** | Overhead-bound / zero compute |
| **Pathological Divergence (`i%8==0 ? 2.999 : 1.0`)** | $133.24\text{ ms}$ | $215.22\text{ ms}$ | **$0.62\times$** | $18.07\text{ ms}$ | $11.91\times$ | **$7.37\times$** | Severe SIMD divergence (12.5% lane utilization) |

---

## 5. Implementation Notes
* **Manual AVX2 Intrinsics:** Manual implementation via `immintrin.h` (`_mm256_*`) logged as an optional optimization backlog item.