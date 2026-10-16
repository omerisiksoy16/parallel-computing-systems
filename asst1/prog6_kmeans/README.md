# Program 6: K-Means Performance Optimization and Multi-Threading

## 1. Performance Profiling and Bottleneck Identification

To determine where execution time was concentrated, I instrumented the main convergence loop in `kMeansThread.cpp` using `CycleTimer::currentSeconds()`.

### Baseline Timing Measurements
* **Dataset Configuration:** $M = 1,000,000$ points, $N = 100$ dimensions, $K = 3$ clusters, $\epsilon = 0.1$
* **Hardware Testbed:** Intel Core i7-14700HX (20 cores, 28 threads), Ubuntu 22.04 LTS (WSL2)

```text
--- Baseline Profiling ---
Assignments: 3579.528 ms  (65.5% of total runtime)
Centroids:    790.122 ms  (14.5% of total runtime)
Costs:       1096.751 ms  (20.0% of total runtime)
---------------------------
Total Time:  5466.487 ms
```

### Analysis of the Bottleneck
The measurements confirmed that `computeAssignments` is the primary performance bottleneck, accounting for approximately $65.5\%$ of overall execution time. 

For each iteration, the algorithm calculates the distance from every data point $m \in [0, M)$ to every centroid $k \in [0, K)$, requiring $M \times K = 3,000,000$ calls to `dist()`. Because each distance evaluation spans $N = 100$ dimensions, this step performs roughly $600,000,000$ floating-point operations per iteration. Under Amdahl's Law, substantial end-to-end acceleration required targeting `computeAssignments`.

---

## 2. Optimization Sequence and Results

### Step 1: Investigating Distance Function Overhead
* **Observation:** In the baseline, `dist()` computes Euclidean distance and calls `sqrt()`.
* **Experiment:** I evaluated the impact of eliminating unnecessary operations within `dist()`.
* **Measured Result:**
  * Baseline Total: `5466.487 ms`
  * Revised Total: `5385.822 ms`
  * Speedup: $1.015\times$ (negligible).
* **Conclusion:** Micro-optimizing the sequential math inside individual `dist()` calls does not address the core bottleneck. The dominant limitation is the sequential processing of $1,000,000$ independent points.

### Step 2: Parallelizing `computeAssignments` Across Datapoints ($M$)
* **Hypothesis:** In `computeAssignments`, calculating the closest centroid for datapoint $m_i$ is completely independent of datapoint $m_j$. Data points only read from shared structures (`args->data` and `args->clusterCentroids`) and write to independent indices of `clusterAssignments[m]`. This makes the workload embarrassingly parallel across the $M$ dimension.
* **Implementation:**
  1. Implemented a worker function (`workerThread`) that processes a disjoint contiguous slice of datapoints $[start, end)$.
  2. Spawned $16$ threads using `std::thread` inside `computeAssignments`.
  3. Partitioned $M = 1,000,000$ datapoints into static blocks (`tasksPerThread = M / 16`) with remainder distribution handled on the final thread.
  4. Executed chunk $0$ on the calling thread to avoid spawning an unnecessary 16th operating system thread, while threads $1 \dots 15$ executed concurrently in the background.
  5. Synchronized all worker threads via `join()` before exiting `computeAssignments`.

---

## 3. Final Performance Evaluation

### Measured Execution Results (Post-Optimization)

```text
--- Optimized Profiling (16 Threads) ---
Assignments:  389.474 ms  (Kernel Speedup: 9.19x)
Centroids:    793.745 ms
Costs:       1055.097 ms
---------------------------
Total Time:  2238.357 ms
```

### Speedup Calculations
* **Kernel Speedup (`computeAssignments`):**
  $$\text{Speedup}_{\text{assignments}} = \frac{3579.528\text{ ms}}{389.474\text{ ms}} = \mathbf{9.19\times}$$

* **Overall Application Speedup:**
  $$\text{Speedup}_{\text{total}} = \frac{5466.487\text{ ms}}{2238.357\text{ ms}} = \mathbf{2.44\times}$$

### Verification
The resulting speedup of **$2.44\times$** successfully exceeds the course requirement of $\ge 2.1\times$. The clustering output was verified using `python3 plot.py`, confirming correct mathematical convergence.
