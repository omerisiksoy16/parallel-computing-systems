# Parallel Computing Systems (Stanford CS149)

This repository contains implementations, performance profiling, and systems engineering reports for [Stanford CS149: Parallel Computing](https://www.google.com/search?q=https%3A%2F%2Fcs149.stanford.edu%2F). 

All benchmarks and scaling experiments were conducted on bare-metal hardware via Linux (Ubuntu 22.04 LTS / WSL2).

### Hardware Testbed
* **Processor:** Intel Core i7-14700HX (20 physical cores: 8 P-cores + 12 E-cores, 28 hardware threads)
* **Microarchitecture:** Raptor Lake-HX (AVX2, FMA3)
* **Caches:** L1d: 672 KiB, L2: 28 MiB, L3: 33 MiB shared
* **Memory Subsystem:** Dual-channel DDR5 (Peak achievable streaming bandwidth: ~85–90 GB/s)

---

## Assignment 1: Multi-Core CPU & SIMD Performance Engineering

Assignment 1 explores the mechanics of parallel execution across multi-core processors, data-level vector parallelism (SIMD), memory hierarchy limits, and cache locality. 

Each program directory contains full source code and a standalone, publication-grade engineering report (`README.md`) detailing profiling methodologies, hypotheses, and benchmark results.

| Program | Topic / Architecture Focus | Key Systems Outcome | Detailed Report |
| :--- | :--- | :--- | :---: |
| **Prog 1: Multi-Threading** | Spatial load imbalance & thread synchronization (`std::thread`) | Diagnosed 50x workload imbalance; implemented cyclic row interleaving to achieve **$6.84\times$ speedup on 8 threads**. |
| **Prog 2: Vector Intrinsics** | SIMD vector registers, lane masking & tree reduction | Implemented vector execution engine and logarithmic span ($O(N/W + \log_2 W)$) tree reduction in simulated SIMD hardware. |
| **Prog 3: ISPC Task Compiler** | SPMD programming model & task scheduling granularity | Swept task granularities ($T=2 \dots 800$), identifying the optimal task-dispatch sweet spot at $T=160$ (**$36.47\times$ speedup**). |
| **Prog 4: Iterative Sqrt** | Control-flow divergence in 8-wide AVX2 vector units | Isolated lockstep SIMD divergence penalty (**$0.62\times$ slowdown** with 12.5% lane utilization) vs. uniform execution (**$48.87\times$ speedup**). |
| **Prog 5: SAXPY & Bandwidth** | Arithmetic intensity & DRAM bus saturation | Evaluated stream bandwidth wall at **$85.42\text{ GB/s}$**; proved microarchitectural Write-Allocate/RFO factor-of-4 memory traffic. |
| **Prog 6: K-Means Optimization** | Performance profiling (`CycleTimer`) & domain decomposition | Profiled algorithm hotspot; parallelized $M=1,000,000$ points across 16 threads (**$9.19\times$ kernel speedup, $2.44\times$ overall**). |

---

## Assignment 2: Building a Task Execution Library (In Progress)
Development of a custom runtime task execution library and dynamic dependency-graph scheduler in modern C++ (`asst2/`).