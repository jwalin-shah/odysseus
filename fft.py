"""Fast Fourier Transform for polynomial multiplication."""
from __future__ import annotations
import cmath
import math


def fft(a: list[complex]) -> list[complex]:
    """Cooley-Tukey FFT. Length must be a power of 2."""
    n = len(a)
    # ODYSSEUS-ALGO-CRASH: base case must cover n==0 and n==1. Without
    # the n==0 short-circuit, fft([]) recurses on `a[0::2]` == [] forever.
    if n <= 1:
        return list(a)
    even = fft(a[0::2])
    odd = fft(a[1::2])
    result = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * cmath.pi * k / n) * odd[k]
        result[k] = even[k] + t
        result[k + n // 2] = even[k] - t
    return result


def ifft(a: list[complex]) -> list[complex]:
    """Inverse FFT."""
    n = len(a)
    conj = [x.conjugate() for x in a]
    result = fft(conj)
    return [x.conjugate() / n for x in result]


def poly_multiply_fft(a: list[int], b: list[int]) -> list[int]:
    """Multiply polynomials a and b using FFT."""
    result_len = len(a) + len(b) - 1
    size = 1
    while size < result_len:
        size <<= 1
    fa = [complex(x) for x in a] + [0j] * (size - len(a))
    fb = [complex(x) for x in b] + [0j] * (size - len(b))
    fa_fft = fft(fa)
    fb_fft = fft(fb)
    fc = [x * y for x, y in zip(fa_fft, fb_fft)]
    result = ifft(fc)
    return [round(x.real) for x in result[:result_len]]


poly_multiply = poly_multiply_fft


def convolve(a: list[float], b: list[float]) -> list[float]:
    """Convolution of two sequences via FFT."""
    result_len = len(a) + len(b) - 1
    size = 1
    while size < result_len:
        size <<= 1
    fa = [complex(x) for x in a] + [0j] * (size - len(a))
    fb = [complex(x) for x in b] + [0j] * (size - len(b))
    fc = [x * y for x, y in zip(fft(fa), fft(fb))]
    result = ifft(fc)
    return [x.real for x in result[:result_len]]
