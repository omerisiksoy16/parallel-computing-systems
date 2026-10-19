# Program 5: SAXPY Performance and Memory Bandwidth Analysis

## 1. Performance and Scaling Analysis

### Measured Execution Results
* **ISPC Single-Threaded (`saxpy_ispc`):** 6.992 ms | 42.622 GB/s | 5.721 GFLOPS
* **ISPC Multi-Tasked (`saxpy_task_ispc`):** 3.489 ms | 85.423 GB/s | 11.465 GFLOPS
* **Observed Speedup:** 2.00x

### Explanation of Performance
The modest 2.00x speedup achieved by multi-core task parallelism is dictated by the algorithm's **Arithmetic Intensity**:

$$\text{Arithmetic Intensity} = \frac{\text{Floating Point Operations (FLOPs)}}{\text{Memory Traffic (Bytes)}}$$

For the SAXPY kernel ($Y[i] = a \cdot X[i] + Y[i]$):
* **Computation per element:** 1 multiplication + 1 addition = 2 FLOPs.
* **Memory traffic per element:** Load $X[i]$ (4 bytes) + Load $Y[i]$ (4 bytes) + Store $result[i]$ (4 bytes) = 12 bytes transferred (or 16 bytes considering cache write-allocation).
* **Arithmetic Intensity:**
  $$\frac{2 \text{ FLOPs}}{16 \text{ bytes}} = 0.125 \text{ FLOP/byte} \quad \left(\text{or } \frac{2}{12} \approx 0.167 \text{ FLOP/byte}\right)$$

On an Intel Core i7-14700HX testbed, peak compute throughput exceeds 1,000 GFLOPS across all execution units, while physical dual-channel DDR5 memory bandwidth peaks around 85–90 GB/s. 

Single-core ISPC already drives 42.622 GB/s through hardware prefetchers. Launching tasks across multiple cores scales memory throughput to 85.423 GB/s, fully saturating the physical memory bus. Because all physical cores share the same memory controller channels, additional threads cannot transfer data any faster once the memory bus reaches saturation. Execution is strictly **memory-bandwidth bound**, and compute units spend the majority of cycles stalled waiting on cache line fills from DRAM.

### Potential for Substantial Improvement
* **Answer:** No.
* **Justification:** Near-linear speedup ($P\times$ on $P$ cores) requires scaling compute throughput independently per core. In SAXPY, performance is constrained by physical DRAM bandwidth, which is a fixed hardware bottleneck shared across all cores. No software optimization, loop restructuring, or task division can exceed the physical throughput of the DDR5 memory channels. Once saturation (~85 GB/s) is reached, software cannot extract further parallel scaling.

---

## 2. Extra Credit 1: Justification of the Factor of 4 in `TOTAL_BYTES`

The total memory traffic reported in `main.cpp` uses:

$$\text{TOTAL\_BYTES} = 4 \times N \times \text{sizeof(float)}$$

Even though the kernel algorithmically loads $X[i]$, loads $Y[i]$, and writes $result[i]$ (3 programmatic operations), the multiplier of 4 accurately reflects hardware memory traffic due to the **Write-Allocate, Write-Back** caching policy implemented in x86-64 microarchitectures:

1. **Write Miss and Read-For-Ownership (RFO):** When the CPU writes to an address in $result[i]$ that is not currently resident in L1/L2 cache (as is typical for large streaming arrays exceeding cache capacity), a write miss occurs. Under write-allocate policy, the memory controller must first load the entire 64-byte cache line containing that address from DRAM into the cache.
2. **Write-Back on Eviction:** After the computed result is stored in the allocated cache line, the line is marked dirty. When subsequent streaming data evicts this line from the cache, the dirty line must be written back to DRAM.

Consequently, writing to the destination array generates two separate memory bus transactions:
* **Stream 1:** Read $X$ from DRAM into cache ($1 \times N \times \text{sizeof(float)}$)
* **Stream 2:** Read $Y$ from DRAM into cache ($1 \times N \times \text{sizeof(float)}$)
* **Stream 3:** Read $result$ from DRAM into cache via Read-For-Ownership ($1 \times N \times \text{sizeof(float)}$)
* **Stream 4:** Write dirty $result$ from cache back to DRAM on eviction ($1 \times N \times \text{sizeof(float)}$)

$$\text{Total Memory Traffic} = (1 + 1 + 1 + 1) \times N \times \text{sizeof(float)} = 4 \times N \times \text{sizeof(float)}$$

---

## 3. Extra Credit 2: Feasibility of Substantial Performance Improvements

### Theoretical Limits
For a standalone kernel processing large arrays streamed from cold DRAM, achieving order-of-magnitude speedups (such as $5\times$ or $10\times$) is physically impossible on existing hardware because execution is bounded by the physical memory bus ceiling (~85 GB/s).

### Architectural Optimizations
1. **Non-Temporal Streaming Stores:**
   Using non-temporal store instructions (e.g., `_mm256_stream_ps` in AVX2) bypasses the cache hierarchy entirely. The CPU writes data directly to write-combining buffers, which stream to DRAM without issuing a Read-For-Ownership (RFO) request. This eliminates Stream 3, reducing total bus traffic from $4N \to 3N$ words. This yields a theoretical $25\%$ bandwidth reduction, translating to an expected theoretical speedup of up to $1.33\times$.
2. **Kernel / Operator Fusion:**
   In real-world numerical computation (e.g., BLAS and deep learning runtimes), standalone SAXPY operations are avoided. Instead, SAXPY is fused into adjacent compute-intensive kernels while intermediate vectors remain resident in L1/L2 cache, eliminating redundant round-trips to main memory.
