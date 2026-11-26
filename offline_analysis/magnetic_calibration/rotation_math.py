"""3x3 rotation math for calibration angles, in pure Python (no numpy).

Matrices are nested lists, row-major. Angles follow the onyx convention:
aerospace intrinsic Z-Y-X yaw, pitch, roll in degrees, body forward/right/down.
"""
from __future__ import annotations

import math
from typing import Sequence

Matrix = Sequence[Sequence[float]]
_SWEEPS = 60
_DIGITS = 4


def polar_rotation(matrix: Matrix) -> tuple[list[list[float]], bool]:
    """The rotation ``R`` of ``matrix = R S`` (S symmetric positive) and whether it mirrors.

    A matrix with a negative determinant has no proper rotation; its mirror
    image ``-matrix`` is decomposed instead and the flag is True.

    Raises:
        ValueError: when ``matrix`` is singular.
    """
    det = determinant(matrix)
    if abs(det) < 1e-300:
        raise ValueError('the calibration correction matrix is singular')
    sign = 1.0 if det > 0 else -1.0
    values, vectors = eigh_symmetric(multiply(transpose(matrix), matrix))
    if min(values) <= 0:
        raise ValueError('the calibration correction matrix is singular')
    scale = [[1 / math.sqrt(values[i]) if i == j else 0.0 for j in range(3)] for i in range(3)]
    inverse_root = multiply(multiply(vectors, scale), transpose(vectors))
    return [[sign * v for v in row] for row in multiply(matrix, inverse_root)], sign < 0


def euler_zyx_deg(rotation: Matrix) -> dict[str, float]:
    """Aerospace Z-Y-X yaw, pitch and roll (degrees, 4 decimals) of a rotation matrix."""
    pitch = -math.asin(max(-1.0, min(1.0, rotation[2][0])))
    return dict(yaw=round(math.degrees(math.atan2(rotation[1][0], rotation[0][0])), _DIGITS),
                pitch=round(math.degrees(pitch), _DIGITS),
                roll=round(math.degrees(math.atan2(rotation[2][1], rotation[2][2])), _DIGITS))


def eigh_symmetric(matrix: Matrix) -> tuple[list[float], list[list[float]]]:
    """Eigenvalues and eigenvector columns of a symmetric 3x3 matrix (cyclic Jacobi)."""
    a = [[float(v) for v in row] for row in matrix]
    vectors = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(_SWEEPS):
        off = sum(a[i][j] ** 2 for i in range(3) for j in range(3) if i != j)
        if off <= 1e-30 * max(1.0, sum(a[i][i] ** 2 for i in range(3))):
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if a[p][q] != 0.0:
                _jacobi_rotate(a, vectors, p, q)
    return [a[i][i] for i in range(3)], vectors


def _jacobi_rotate(a: list[list[float]], vectors: list[list[float]], p: int, q: int) -> None:
    """Zero ``a[p][q]`` with one Jacobi rotation, accumulating it into ``vectors`` (in place)."""
    theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
    t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1))
    c = 1 / math.sqrt(t * t + 1)
    s = t * c
    for row in a:
        row[p], row[q] = c * row[p] - s * row[q], s * row[p] + c * row[q]
    a[p], a[q] = [c * x - s * y for x, y in zip(a[p], a[q])], [s * x + c * y for x, y in zip(a[p], a[q])]
    for row in vectors:
        row[p], row[q] = c * row[p] - s * row[q], s * row[p] + c * row[q]


def multiply(a: Matrix, b: Matrix) -> list[list[float]]:
    """The 3x3 product ``a b``."""
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transpose(a: Matrix) -> list[list[float]]:
    """The transpose of a 3x3 matrix."""
    return [[a[j][i] for j in range(3)] for i in range(3)]


def determinant(a: Matrix) -> float:
    """The determinant of a 3x3 matrix."""
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
