# server/engine/cuda_engine.py
# Optional CUDA tensor computation demonstration using PyTorch.
# This module is completely independent of the video rendering pipeline.

import time
from shared.models import TensorJobRequest, TensorJobResult
from server.utils.logger import get_logger

logger = get_logger("cuda_engine")


def run_tensor_computation(request: TensorJobRequest) -> TensorJobResult:
    """
    Perform matrix multiplication using CUDA if available, CPU otherwise.
    Returns computation time and actual device used.
    """
    try:
        import torch  # type: ignore

        cuda_available = torch.cuda.is_available()

        if cuda_available and request.execution_mode in ("auto", "gpu"):
            device = torch.device("cuda")
            device_label = f"CUDA ({torch.cuda.get_device_name(0)})"
        else:
            device = torch.device("cpu")
            device_label = "CPU"

        logger.info(f"Tensor computation on {device_label} | "
                    f"Shape: ({request.rows_a}x{request.cols_a}) x "
                    f"({request.cols_a}x{request.cols_b})")

        a = torch.randn(request.rows_a, request.cols_a, device=device)
        b = torch.randn(request.cols_a, request.cols_b, device=device)

        # Warm up
        _ = torch.matmul(a, b)
        if cuda_available and str(device) == "cuda":
            torch.cuda.synchronize()

        start = time.perf_counter()
        result = torch.matmul(a, b)
        if cuda_available and str(device) == "cuda":
            torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - start) * 1000

        result_sum = float(result.sum().item())
        shape_str = f"({request.rows_a}x{request.cols_b})"

        logger.info(f"Computation done in {elapsed_ms:.2f}ms on {device_label}")

        return TensorJobResult(
            execution_device=device_label,
            computation_time_ms=elapsed_ms,
            matrix_shape=shape_str,
            result_sum=result_sum,
            cuda_available=cuda_available,
        )

    except ImportError:
        logger.warning("PyTorch not installed — using pure Python fallback")
        return _python_fallback(request)


def _python_fallback(request: TensorJobRequest) -> TensorJobResult:
    """Minimal matrix multiply fallback without NumPy or PyTorch."""
    import random
    r, c, k = request.rows_a, request.cols_b, request.cols_a

    # Limit size to avoid hanging on huge matrices in fallback mode
    r = min(r, 64)
    c = min(c, 64)
    k = min(k, 64)

    a = [[random.gauss(0, 1) for _ in range(k)] for _ in range(r)]
    b = [[random.gauss(0, 1) for _ in range(c)] for _ in range(k)]

    start = time.perf_counter()
    result = [[sum(a[i][p] * b[p][j] for p in range(k)) for j in range(c)] for i in range(r)]
    elapsed_ms = (time.perf_counter() - start) * 1000

    total = sum(result[i][j] for i in range(r) for j in range(c))

    return TensorJobResult(
        execution_device="CPU (Python fallback)",
        computation_time_ms=elapsed_ms,
        matrix_shape=f"({r}x{c})",
        result_sum=total,
        cuda_available=False,
    )
