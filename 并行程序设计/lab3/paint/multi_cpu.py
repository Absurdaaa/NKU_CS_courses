# baseline
# Guess time:0.300993seconds

# pthread-o2
# Guess time:0.392677seconds

# Guess time:0.30991seconds

# Guess time:0.283852seconds

# Guess time:0.281583seconds

# Guess time:0.303205seconds

# Guess time:0.311211seconds

# Guess time:0.325405seconds

# Guess time:0.344234seconds


# openmp-o2

# Guess time:0.324796seconds

# Guess time:0.260703seconds

# Guess time:0.233602seconds

# Guess time:0.222322seconds

# Guess time:0.216787seconds

# Guess time:0.210932seconds

# Guess time:0.207917seconds

# Guess time:0.218134seconds

import matplotlib.pyplot as plt
import numpy as np

# Extract data
baseline_time = 0.300993

pthread_times = [0.392677, 0.30991, 0.283852, 0.281583, 0.303205, 0.311211, 0.325405, 0.344234]
openmp_times = [0.324796, 0.260703, 0.233602, 0.222322, 0.216787, 0.210932, 0.207917, 0.218134]

# Calculate speedup
pthread_speedup = [baseline_time / time for time in pthread_times]
openmp_speedup = [baseline_time / time for time in openmp_times]

# Thread counts
threads = list(range(1, 9))

# Create the plot
plt.figure(figsize=(10, 6))

# Plot data points
plt.plot(threads, pthread_speedup, marker='o', linewidth=2, markersize=8, label='Pthread-O2')
plt.plot(threads, openmp_speedup, marker='s', linewidth=2, markersize=8, label='OpenMP-O2')

# Customize plot
plt.title('Speedup vs. Number of Threads', fontsize=16)
plt.xlabel('Number of Threads', fontsize=14)
plt.ylabel('Speedup (Baseline/Parallel)', fontsize=14)
plt.xticks(threads)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(fontsize=12)

# Set y-axis limit based only on actual data
max_speedup = max(max(pthread_speedup), max(openmp_speedup))
plt.ylim(0, max_speedup * 1.1)

# Add annotations
plt.annotate(f'Baseline (Serial-O2): {baseline_time:.6f}s', 
             xy=(0.02, 0.02), xycoords='figure fraction', 
             fontsize=10, bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

# Save and show the plot
plt.tight_layout()
plt.savefig('/Users/linshangjin/Downloads/paint/cpu_comparison.png', dpi=300)
plt.show()