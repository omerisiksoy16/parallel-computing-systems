# Program 3: Multi-Core ISPC Parallelism

## 1. System Specifications & Experimental Environment
All benchmarks were compiled with `-O3` optimization flag on a 64-bit Linux environment under WSL2.
- **CPU:** Intel(R) Core(TM) i7-14700HX
- **Topology:** 14 Physical Cores (8 Performance-Cores + 12 Efficient-Cores), 28 Logical Threads (vCPUs)
- **Caches:** L1d: 672 KiB, L1i: 448 KiB, L2: 28 MiB, L3: 33 MiB (shared)
- **Sequential Baseline Runtime:** ~110.2 - 114.0 ms (View 1, 1200x800)

---

## 2. Single-Core ISPC Vectorization (Question 1)

### Benchmark Results (Single-Core, No Tasks):
- **Sequential Baseline (`mandelbrotSerial`):** `112.15 ms`
- **Single-Core ISPC (`mandelbrot_ispc`):** `32.19 ms`
- **Observed Speedup:** **`3.48x`**

### Analysis: Expected vs. Observed Speedup
* **Maximum Theoretical Speedup:** The ISPC compiler is configured to emit 8-wide AVX2 instructions (`--target=avx2`). Executing on a single physical core, the theoretical arithmetic maximum speedup is **`8.00x`** (one vector instruction processes 8 single-precision floats simultaneously).
* **Why Observed Speedup is Lower (3.48x vs. 8.00x):**
  This discrepancy is primarily driven by **SIMD / Control Divergence**:
  1. **Lock-Step Lane Execution:** ISPC groups 8 program instances into a single vector "gang." All 8 lanes execute instructions synchronously.
  2. **Complex Plane Workload Disparity:** In the Mandelbrot calculation, interior points require the full `maxIterations` (1000 iterations), whereas points far outside the boundary escape in 1–2 iterations.
  3. **Boundary Region Inefficiency:** The most computationally demanding regions are the intricate fractal boundaries where exterior (fast) and interior (slow) pixels lie adjacent to one another within the same 8-pixel gang. In these gangs, lanes that escape early must be masked off (disabled), but the SIMD execution pipeline continues running iterations until the slowest lane finishes.
  4. **Confirmation via View Comparison:** Comparing View 1 with View 2 confirms this: zoomed-in views with more homogeneous iteration counts across adjacent pixels yield higher average lane utilization and greater speedup than views dominated by high-frequency fractal edges.

---

## 3. Initial Multi-Core Task Execution (Question 2)

### Benchmark Results (Default 2 Tasks):
- **Sequential Baseline:** `112.10 ms`
- **Single-Core ISPC:** `32.88 ms` (3.41x)
- **Multi-Core ISPC (`--tasks`, 2 Tasks):** `16.80 ms`
- **Speedup over Sequential:** **`6.67x`**
- **Speedup over Single-Core ISPC:** **`1.96x`** ($\approx 32.88\text{ ms} / 16.80\text{ ms}$)

### Discussion:
Dividing the image into 2 horizontal tasks yields a near-perfect $2\times$ scaling over single-core ISPC ($1.96\text{x}$), demonstrating that two physical cores are executing 8-wide SIMD instructions concurrently with minimal inter-core interference. However, 26 logical threads on the machine remain completely idle.

---

## 4. Task Granularity Optimization & Sweet Spot Sweep (Question 3)

To exceed the target threshold of **32x speedup**, the task partitioning in `mandelbrot_ispc_withtasks()` was parameterized to sweep across task counts from $T = 2$ to $T = 800$ on the $800$-row image:

$$\text{rowsPerTask} = \frac{\text{height}}{\text{numTasks}}$$

### Empirical Task Sweep Benchmark Table:

| Number of Tasks ($T$) | Rows per Task | Multi-Core Runtime (ms) | Speedup (vs. Serial) | System Observation |
| :---: | :---: | :---: | :---: | :--- |
| **2** | 400 | 16.80 ms | **6.67x** | Massive hardware under-utilization (26 threads idle) |
| **16** | 50 | 5.39 ms | **20.45x** | Utilizing primary P-cores |
| **32** | 25 | 4.17 ms | **27.22x** | Exceeds hardware thread count; work-stealing active |
| **40** | 20 | 3.85 ms | **29.65x** | Balanced chunk size across cores |
| **80** | 10 | 3.60 ms | **31.47x** | Approaching optimal hardware saturation |
| **160** | **5** | **3.06 ms** | **36.47x** | 🏆 **PEAK SWEET SPOT! (Shattered 32x goal)** |
| **200** | 4 | 3.58 ms | **31.07x** | Diminishing returns & task overhead creep |
| **400** | 2 | 3.82 ms | **29.26x** | Task dispatch latency impacts throughput |
| **800** | 1 | 10.21 ms | **10.97x** | 💥 **Collapse (Scheduling overhead dominates)** |

### Why Did 160 Tasks Yield the Best Performance?
1. **Dynamic Load Balancing via Over-Decomposition:** Setting $T = 160$ provides $\sim 5.7$ tasks per hardware thread ($160 / 28 \approx 5.7$). ISPC’s user-space work-stealing thread pool ensures that cores finishing easy exterior tasks immediately steal remaining interior tasks, eliminating the static load imbalance seen in Program 1.
2. **Sufficient Computational Granularity (5 Rows/Task):** A 5-row slice contains enough arithmetic intensity to amortize the cost of task creation, atomic queue synchronization, and cache-line allocation.
3. **The Collapse at 800 Tasks (The Overhead Wall):** When $T = 800$, each task computes only 1 single row. A single row of exterior pixels executes in under a microsecond. The runtime overhead of allocating task descriptors, acquiring queue locks, and synchronizing worker threads exceeds the computation itself, causing speedup to collapse from **36.47x down to 10.97x**.

---

## 5. Extra Credit: OS Threads vs. ISPC Tasks (Question 4)

| Dimension | OS Threads (`std::thread` / `pthread`) | ISPC Tasks (`launch`) |
| :--- | :--- | :--- |
| **Level of Abstraction** | Operating system kernel-level execution context | Lightweight user-space work descriptor / job |
| **Stack Allocation** | Dedicated OS stack per thread (typically 2 MB to 8 MB) | Shares the pre-allocated execution stack of worker threads |
| **Creation Cost** | Heavyweight (`clone()` / `pthread_create` kernel syscalls) | Microscopic (pushing a struct onto a lock-free queue) |
| **Scheduling Model** | Preemptive OS kernel scheduler with full register context switching | Cooperative work-stealing thread pool in user space |

### Thought Experiment: 10,000 Threads vs. 10,000 Tasks
* **10,000 OS Threads (`std::thread`):**  
  Spawning 10,000 OS threads requires reserving $\sim 20\text{ GB} - 80\text{ GB}$ of virtual address space solely for thread stacks. The operating system will typically crash with `pthread_create failed: Resource temporarily unavailable`. If it survives, the kernel scheduler wastes nearly all CPU cycles swapping registers, invalidating TLBs, and thrashing L1/L2 caches during context switches.
* **10,000 ISPC Tasks (`launch[10000]`):**  
  The ISPC runtime maintains a fixed number of worker threads equal to the CPU's core count (28 threads). The 10,000 tasks are simply small metadata structs placed in a user-space queue ($\sim \text{a few hundred kilobytes}$ of RAM). Worker threads continuously execute tasks from the queue with zero OS context switching, running smoothly to completion at full hardware throughput.

---

## 6. The Smart-Thinking Student's Question: Why Both `foreach` AND `launch`?

> **Question:** Why does ISPC provide two distinct mechanisms (`foreach` and `launch`) for expressing independent work? Couldn't the compiler simply partition the iterations of `foreach` across all CPU cores and emit the appropriate SIMD code automatically?

### The Architectural Answer:
The separation of `foreach` and `launch` reflects a deliberate design choice based on the fundamental physics of computer architecture:

1. **Mapping to Fundamentally Different Hardware Models (SIMD vs. MIMD):**
   * **`foreach` maps to SIMD (Within a Core):** All program instances share a **single Instruction Pointer (Program Counter)** and execute in lock-step across hardware vector lanes. Branches are handled via hardware masking, with zero synchronization overhead between lanes.
   * **`launch` maps to MIMD (Across Cores):** Each task runs on an asynchronous physical CPU core with its own independent instruction pointer, register file, and execution pipeline.
   * Conflating the two would obscure the reality that inter-core communication has a non-zero latency cost, whereas intra-core vector lanes communicate at zero latency.

2. **Programmer Control Over Granularity:**
   As demonstrated in our empirical sweep ($T=2 \dots 800$), dividing work across cores requires tuning the **task granularity**. A compiler cannot infer at compile-time how many CPU cycles an iteration will take (due to inputs like divergent fractal iterations). By keeping `launch` explicit, the programmer can choose a task size that amortizes thread-scheduling overhead, while `foreach` handles fine-grained vectorization within that task.

3. **Cache Locality and Memory Hierarchy:**
   A single core running an entire task sequentially across SIMD lanes achieves maximum L1/L2 cache locality. If the compiler were to blindly divide `foreach` iterations across arbitrary cores, it could easily cause false sharing and cache-line bouncing across CPU sockets.

4. **Composability with Existing Multi-Threaded Frameworks:**
   Many production systems (such as game engines, database query engines, and rendering pipelines) already have sophisticated thread schedulers (e.g., Intel oneTBB, OpenMP, custom job systems). By separating `foreach` from `launch`, ISPC allows developers to use ISPC purely as a high-performance vector code generator (`foreach`) embedded inside their own existing thread pools without forcing them to adopt the ISPC task runtime.