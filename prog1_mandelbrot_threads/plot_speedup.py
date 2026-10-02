import matplotlib.pyplot as plt

# Measured benchmark data (View 1)
threads = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]
speedup = [1.00, 1.96, 1.60, 2.41, 2.38, 3.14, 3.26, 3.84, 4.11, 4.64, 4.81, 5.36, 5.65, 6.10, 6.23]

# Theoretical linear speedup baseline (y = x)
ideal_speedup = threads

plt.figure(figsize=(10, 6))

# Plot ideal baseline
plt.plot(threads, ideal_speedup, label='Ideal Linear Speedup', 
         color='gray', linestyle='--', alpha=0.7, linewidth=2)

# Plot actual measured speedup
plt.plot(threads, speedup, label='Measured Speedup (Spatial Block Decomposition)', 
         color='#1f77b4', marker='o', linewidth=2.5, markersize=6)

# Annotate the load imbalance anomaly at thread 3
plt.annotate('Load Imbalance Dip!\n(1.96x -> 1.60x)', 
             xy=(3, 1.60), xytext=(4.5, 1.0),
             arrowprops=dict(facecolor='#d62728', shrink=0.08, width=1.5, headwidth=8),
             fontsize=10, fontweight='bold', color='#d62728',
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#d62728", lw=1.5))

# Plot styling & English labels
plt.title('Stanford CS149: Mandelbrot Speedup vs. Thread Count (View 1)\nHardware: Intel Core i7-14700HX (Spatial Block Decomposition)', 
          fontsize=12, fontweight='bold', pad=15)
plt.xlabel('Thread Count', fontsize=11)
plt.ylabel('Speedup (Factor over Sequential Baseline)', fontsize=11)
plt.xticks(threads)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(fontsize=10, loc='upper left')

# Export high-resolution image
output_filename = 'speedup_block.png'
plt.tight_layout()
plt.savefig(output_filename, dpi=300)
print(f"Plot successfully saved to: {output_filename}")
