# Program 2: Vectorizing Code Using SIMD Intrinsics

## 1. Overview & Experimental Setup
In this lab, scalar computations were vectorized using CS149's simulated SIMD vector intrinsics (`CS149intrin.h`).
The primary objectives were:
1. Transforming sequential exponentiation (`clampedExpSerial`) into a vectorized routine (`clampedExpVector`) supporting arbitrary array sizes $N$ and vector widths $W$.
2. Analyzing the impact of vector register width ($W \in \{2, 4, 8, 16\}$) on **Vector Utilization** and dynamic instruction counts.
3. Implementing an optimal tree-reduction array summation (`arraySumVector`) achieving sub-linear span.

All tests were benchmarked with $N = 10,000$ elements on an **Intel(R) Core(TM) i7-14700HX** under Ubuntu (WSL2).

---

## 2. Vector Width Sweep & Utilization Results (Question 2)

| Vector Width ($W$) | Total Vector Instructions | Vector Utilization (%) | Utilized Vector Lanes | Total Vector Lanes |
| :---: | :---: | :---: | :---: | :---: |
| **2** | 162,515 | **87.6%** | 284,622 | 325,030 |
| **4** | 94,571 | **82.3%** | 311,252 | 378,284 |
| **8** | 51,627 | **79.6%** | 328,624 | 413,016 |
| **16** | 26,967 | **78.3%** | 337,864 | 431,472 |

---

## 3. Analysis: Does Vector Utilization Increase or Decrease? Why?

### Finding:
**Vector Utilization monotonically decreases as vector width ($W$) increases** (dropping from **87.6%** at $W=2$ down to **78.3%** at $W=16$).

### Architectural & Mathematical Root Cause:
This behavior is a textbook demonstration of **SIMD / Branch Divergence**:
1. **Lock-Step Execution:** A SIMD vector unit executes a single instruction across all $W$ lanes simultaneously. In `clampedExpVector`, each lane computes $x^{\text{exp}}$ by decrementing its exponent until reaching zero.
2. **Worst-Case Bottleneck per Chunk:** The while-loop for any chunk of size $W$ must iterate until the **maximum exponent in that specific chunk** reaches zero:
   $$\text{Iterations}(\text{chunk}) = \max_{k \in \text{chunk}}(\text{exponent}_k)$$
3. **Probability of Outliers:** As the vector width expands from 2 to 16:
   - The probability that a chunk contains at least one large exponent outlier increases significantly.
   - Lanes with small exponents finish early and are masked off (disabled with 0 in `mask2`).
   - While the vector multiplier continues to fire for the remaining active lanes, disabled lanes sit idle, driving down the ratio of active lanes to total lanes ($\text{Utilized Lanes} / \text{Total Lanes}$).

---

## 4. Total Dynamic Instruction Scaling

While utilization slightly decreases, **Total Vector Instructions drop dramatically**:
- Moving from $W=2$ to $W=16$ reduces total instruction count from **162,515 down to 26,967** (a **~6.03x reduction** in executed instructions).
- **Takeaway:** Even with a modest ~9% loss in lane utilization (due to divergence), wider SIMD execution still delivers substantial net performance gains because each instruction processes proportionally more data elements per cycle.

---

## 5. Extra Credit: `arraySumVector` & Complexity Analysis

### Implementation Strategy:
Instead of performing an expensive horizontal reduction inside the main loop (which would result in an inefficient $O\left(\frac{N}{W} \log_2 W\right)$ complexity), the problem was decomposed into two distinct phases:
1. **Vertical Accumulation (Loop Phase):** Summing contiguous chunks into a running vector accumulator `y` using purely vertical vector addition (`_cs149_vadd_float`).
2. **Horizontal Reduction Tree (Post-Loop Phase):** Folding the final accumulator vector into a scalar sum using an interleaved binary tree reduction via alternating `_cs149_hadd` and `_cs149_interleave` operations.

### Complexity Breakdown:

| Metric | Sequential (`arraySumSerial`) | Vectorized (`arraySumVector`) |
| :--- | :---: | :---: |
| **Time Complexity (Operations)** | $O(N)$ scalar operations | $O\left(\frac{N}{W} + \log_2 W\right)$ vector operations |
| **Span / Depth** | $O(N)$ | $O\left(\frac{N}{W} + \log_2 W\right)$ |
| **Auxiliary Space Complexity** | $O(1)$ scalar | $O(1)$ (fixed vector registers on stack) |

For $N = 10,000$ and $W = 16$:
- Loop iterations: $10,000 / 16 = 625$ vertical additions.
- Reduction tree: $\log_2(16) = 4$ horizontal steps.
- Total operations: **629 vector instructions** vs. **10,000 scalar instructions** (~16x algorithmic span reduction).

---

## 6. Key Architectural Takeaways
1. **Predicated/Masked Execution:** SIMD architectures handle conditional branches without branch misprediction penalties by converting control divergence into data masking, at the cost of ALU idle time on inactive lanes.
2. **Accumulate Vertically, Reduce Horizontally:** In reduction algorithms, horizontal SIMD operations should be deferred to the boundary, maximizing high-throughput vertical vector arithmetic.