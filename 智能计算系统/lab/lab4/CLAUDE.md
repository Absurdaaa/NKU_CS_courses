# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is Lab 4 (Chapter 5) of the "智能计算系统" (Intelligent Computing Systems) course, focusing on Cambricon MLU (Machine Learning Unit) programming with BANG C. It contains two experiments:

- **exp_5_1**: Building a custom PyTorch sigmoid operator on MLU using MLUExtension
- **exp_5_2**: Progressive optimization of matrix multiplication on MLU (6 stages from scalar to pipelined vectorized)

## Build & Test

### exp_5_1 (Custom PyTorch MLU Operator)

```bash
cd exp_5_1_custom_pytorch_mlu_op
python setup.py install          # compile and install the custom op
python -m pytest tests/          # run correctness and benchmark tests
```

This compiles `.mlu` (BANG C device code) and `.cpp` (host code) into a shared library via `MLUExtension`/`BuildExtension` from `torch_mlu`. The host code includes `ATen/Tensor.h`, `aten/operators/bang/bang_kernel.h`, and registers the op via pybind11.

### exp_5_2 (MatMul Optimization)

```bash
cd exp_5_2_matmul_opt
source env.sh                     # export NEUWARE_HOME and PATH
bash test.sh                      # compile and run all 6 variants
```

The `test.sh` script uses `cncc` (Cambricon BANG C compiler) with `--bang-arch=compute_30 -O3`. Each `.mlu` file is a self-contained program with a `main()` that compares the MLU result against a CPU reference.

The toolchain requires Cambricon Neuware SDK. `env.sh` sets `NEUWARE_HOME=/torch/neuware_home` and adds `/bin`, `/lib64`, `/lib` to PATH/LD_LIBRARY_PATH.

## Architecture

### exp_5_1 Directory Structure

```
mlu_custom_ext/
  mlu/
    include/
      bang_sigmoid_sample.h    # C++ template declaration for kernel entry
      customed_ops.h           # pybind11 torch::Tensor API declaration
      kernel.h                 # Device-side macros (NFU_ALIGN_SIZE, MAX_NRAM_SIZE, etc.)
    src/
      bang_sigmoid.cpp         # Host-side wrapper: gets MLU pointers, calls kernel, pybind11 module def
      bang_sigmoid_sample.mlu  # BANG C kernel: NRAM buffer management, __memcpy_async, __bang_sigmoid
  mlu_functions/
    mlu_functions.py           # Python torch.autograd.Function for sigmoid (forward + backward)
  tests/
    test_sigmoid.py            # Correctness tests (forward/backward)
    test_sigmoid_benchmark.py  # Timing with torch.mlu.Event warmup
setup.py                       # MLUExtension build configuration
```

The data flow for a sigmoid op call:
1. Python `sigmoid(x)` → `sigmoid_function.apply(x)` (PyTorch autograd hook)
2. → `active_sigmoid_mlu(x)` (C++ host, via pybind11) — gets MLU data ptr from tensor, allocates output
3. → `bang_sigmoid_kernel_entry(queue, dst, src, count)` — sets up `cnrtDim3_t` and launches kernel
4. → `bang_sigmoid_kernel<T>` (BANG C device code) — NRAM tiling with DMA via `__memcpy_async`, `__bang_sigmoid` compute, `__sync_io`/`__sync_compute` barriers

Key MLU/BANG patterns in this codebase:
- Memory hierarchy: GDRAM (global) ↔ NRAM (on-chip, shared) via `__memcpy_async` + `__sync_io()`
- Compute/IO overlap: `__sync_compute()` separates compute from subsequent DMA
- Architecture detection: `__BANG_ARCH` macros (270, 290, 370) for conditional code; `kernel.h` defines `MAX_NRAM_SIZE` with 128KB reserved for compiler
- `__mlu_entry__` for standalone `.mlu` programs; `__mlu_global__` for kernels called from host

### exp_5_2 Optimization Progression

Each `.mlu` file is a standalone program (CPU reference + MLU kernel + `main()` with timing). The six stages:

| File | Key technique | M×N×K |
|------|--------------|-------|
| `01_scalar.mlu` | Basic scalar loops (no MLU data movement) | 128×256×128 |
| `02_scalar_nram.mlu` | Scalar compute + NRAM buffering | 128×256×128 |
| `03_vector_nram.mlu` | `__bang_matmul` + NRAM | 128×256×128 |
| `04_vector_nram_blocks.mlu` | Tiled matmul with NRAM blocks | 524288×256×128 |
| `05_vector_nram_blocks_pipe3.mlu` | 3-stage software pipeline (compute/IO overlap) | 524288×256×128 |
| `06_vector_sram_unions_pipe5.mlu` | SRAM unions + 5-stage pipeline | 524288×256×128 |

Hardware: MLU370-X8 or MLU370-X4. The K dimension is fixed at 128 (a common constraint in MLU matmul optimizations).

## Notes

- Many source files contain `TODO` placeholders with `_______________` blanks — these are student exercise fill-in spots. They are present in `.mlu` kernels, `.cpp` host code, and Python test files.
- The `.pdf` in the root is the course textbook chapter covering these experiments.
- `cncc` handles both host C++ and device BANG C code compilation. For MLUExtension builds, host-side C++ files that include `torch/extension.h` MUST have their include paths set via `extra_compile_args.cncc` (not `include_dirs`), because `cncc` cannot process C++ headers from PyTorch.
