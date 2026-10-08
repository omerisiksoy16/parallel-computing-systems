# Program 4: Parallel Sqrt via ISPC Task & Vector Execution

## Overview
This benchmark evaluates the arithmetic performance and scaling characteristics of an iterative Newton-Raphson square root algorithm ($1/\sqrt{x}$) implemented using:
1. Scalar sequential C++ execution (`sqrtSerial`).
2. Single-core SIMD vectorization via the Intel SPMD Program Compiler (`sqrt_ispc`, AVX2 8-wide).
3. Multi-core task parallelism combined with SIMD vectorization (`sqrt_ispc_task`).

All benchmarks were executed on an **Intel Core i7-14700HX** (20 physical cores: 8 P-cores + 12 E-cores, 28 hardware threads) running Ubuntu 22.04 LTS via WSL2. The compiler target is AVX2 (`--target=avx2`), generating 8-wide 32-bit floating-point SIMD vector instructions.

---

## 1. Baseline Performance & Scaling Analysis

### Measured Execution Times (Random Input: [0.001, 2.999])
* **Sequential Baseline ($T_{\text{serial}}$):** `501.097 ms`
* **ISPC Single-Threaded ($T_{\text{ispc}}$):** `135.868 ms`
* **ISPC Multi-Tasked ($T_{\text{task}}$):** `10.984 ms`

### Speedup Decomposition

#### 1. SIMD Parallelization Speedup
$$\text{Speedup}_{\text{SIMD}} = \frac{T_{\text{serial}}}{T_{\text{ispc}}} = \frac{501.097 \text{ ms}}{135.868 \text{ ms}} = \mathbf{3.69\times}$$

On an 8-wide SIMD architecture, the theoretical peak speedup is $8.0\times$. The measured $3.69\times$ speedup is bounded by control-flow divergence: random input values require varying numbers of Newton-Raphson iterations to converge. Under lockstep SIMD execution, a vector lane must remain active until the slowest lane in its 8-element gang finishes, forcing converged lanes to sit idle via hardware lane masking.

#### 2. Multi-Core Parallelization Speedup
$$\text{Speedup}_{\text{multi-core}} = \frac{T_{\text{ispc}}}{T_{\text{task}}} = \frac{135.868 \text{ ms}}{10.984 \text{ ms}} = \mathbf{12.37\times}$$

Distributing execution across the physical cores via the ISPC task runtime achieves a $12.37\times$ scaling factor over single-core vector execution on the testbed.

#### 3. Aggregate Speedup
$$\text{Speedup}_{\text{aggregate}} = \frac{T_{\text{serial}}}{T_{\text{task}}} = \frac{501.097 \text{ ms}}{10.984 \text{ ms}} = \mathbf{45.62\times}$$

$$\text{Total Speedup} = \text{Speedup}_{\text{SIMD}} \times \text{Speedup}_{\text{multi-core}} = 3.69\times \times 12.37\times \approx 45.62\times$$

---

## 2. Best-Case Input: Maximizing Speedup

To maximize relative speedup over the scalar baseline, input data must satisfy two architectural requirements:
1. **Zero Vector Lane Divergence:** All 8 lanes in an AVX2 vector register must perform identical iteration counts (100% active lane utilization).
2. **High Arithmetic Intensity:** Maximize the number of loop iterations to amortize loop initialization, memory load latency, and function call overhead.

The algorithm uses initial guess $x_0 = 1.0\text{f}$. Input values near $3.0\text{f}$ induce maximum initial error $\vert{}x_0^2 \cdot x - 1.0\text{f}\vert{}$, requiring the maximum number of iterations before reaching the convergence threshold.

### Benchmark Results (`values[i] = 2.998f`)
* **Sequential Baseline ($T_{\text{serial}}$):** `808.205 ms`
* **ISPC Single-Threaded ($T_{\text{ispc}}$):** `194.603 ms` (**4.15x** speedup)
* **ISPC Multi-Tasked ($T_{\text{task}}$):** `16.538 ms` (**48.87x** speedup)

### Architectural Analysis
* **SIMD Speedup:** Increased from $3.69\times$ to **$4.15\times$**. Every lane in every vector executes the exact same number of iterations. No lane is masked off prematurely.
* **Multi-Core Scaling:**
  $$\text{Speedup}_{\text{multi-core}} = \frac{194.603 \text{ ms}}{16.538 \text{ ms}} = \mathbf{11.77\times}$$
  Multi-core scaling remains invariant ($\sim 12\times$) because thread chunking across cores is independent of data-level vector lane convergence.

---

## 3. Worst-Case Input: Minimizing Speedup (SIMD Divergence Pathologies)

To minimize SIMD speedup, the input pattern must maximize control-flow divergence across adjacent elements packed into each 8-wide AVX2 vector.

### Tested Configurations

#### A. Zero-Work Convergence (`values[i] = 1.0f`)
* **Sequential Baseline:** `8.057 ms`
* **ISPC Single-Threaded:** `6.655 ms` (**1.21x**)
* **ISPC Multi-Tasked:** `2.484 ms` (**3.24x**)
* **Analysis:** With initial guess $x_0 = 1.0\text{f}$, initial error is zero. The loop terminates on iteration 0 across all lanes. Memory access latency and runtime task dispatch dominate total runtime, severely constraining parallel scaling (Amdahl's Law).

#### B. Pathological Vector Divergence (`if (i % 8 == 0) values[i] = 2.999f; else values[i] = 1.0f;`)
* **Sequential Baseline ($T_{\text{serial}}$):** `133.242 ms`
* **ISPC Single-Threaded ($T_{\text{ispc}}$):** `215.216 ms` (**0.62x** — **38% Slowdown**)
* **ISPC Multi-Tasked ($T_{\text{task}}$):** `18.067 ms` (**7.37x**)

### Root-Cause Analysis of the Slowdown
1. **Scalar Behavior:** For 7 out of every 8 array elements (`values[i] = 1.0f`), the scalar code exits immediately after iteration 0. Only 1 out of 8 elements executes the full iteration loop. Total serial work is approximately $\frac{1}{8} N \times \text{iterations}$.
2. **SIMD AVX2 Behavior:** An 8-wide vector packs indices $[8k \dots 8k+7]$. Lane 0 requires full iterations, while lanes 1–7 terminate on iteration 0. Under lockstep SIMD execution:
   * The vector instruction pointer cannot exit the loop until **all** active lanes satisfy the exit condition.
   * Lanes 1–7 are masked off (`mask = 0`), idling and consuming execution cycles.
   * **Active Vector Lane Utilization drops to $1/8 = 12.5\%$**.
3. **True Slowdown (0.62x):** Because AVX2 executes the full loop duration for every vector while incurring mask generation, branch testing (`vptest`), and pack/unpack overhead, single-core ISPC is slower than unvectorized scalar execution.
4. **Decoupled Multi-Core Scaling:** Despite the SIMD breakdown, multi-core task scheduling maintains its efficiency:
   $$\frac{215.216 \text{ ms}}{18.067 \text{ ms}} = \mathbf{11.91\times}$$
   Aggregate speedup collapses to $7.37\times$ entirely due to the collapsed SIMD factor ($0.62 \times 11.91 \approx 7.37$).

---

## 4. Summary Benchmark Matrix

| Experiment | Input Pattern | $T_{\text{serial}}$ | $T_{\text{ispc}}$ | SIMD Speedup | $T_{\text{task}}$ | Multi-Core Scaling | Aggregate Speedup |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline (Q1)** | Random $[0.001, 2.999]$ | 501.10 ms | 135.87 ms | **3.69x** | 10.98 ms | 12.37x | **45.62x** |
| **Best Case (Q2)** | Uniform `2.998f` | 808.21 ms | 194.60 ms | **4.15x** | 16.54 ms | 11.77x | **48.87x** |
| **Worst Case (Q3)** | `i % 8 == 0 ? 2.999f : 1.0f` | 133.24 ms | 215.22 ms | **0.62x** | 18.07 ms | 11.91x | **7.37x** |

---

## 5. Implementation Notes
* **Manual AVX2 Intrinsics:** Manual implementation via `immintrin.h` (`_mm256_*`) logged as an optional optimization backlog item.