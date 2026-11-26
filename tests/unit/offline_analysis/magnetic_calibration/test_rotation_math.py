"""3x3 rotation math behind the Offline Data angle window (pure Python, runs on the Pi).

Rotations are built from aerospace Z-Y-X yaw/pitch/roll here independently of
``rotation_math`` so the Euler extraction is checked against a known matrix.
"""
import math
import unittest

from offline_analysis.magnetic_calibration.rotation_math import (determinant, eigh_symmetric, euler_zyx_deg, multiply, polar_rotation,
                                    transpose)

TOLERANCE = 1e-9


def zyx(yaw_deg, pitch_deg, roll_deg):
    """The body-to-level rotation R = Rz(yaw) Ry(pitch) Rx(roll) for angles in degrees."""
    y, p, r = (math.radians(a) for a in (yaw_deg, pitch_deg, roll_deg))
    rz = [[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]]
    ry = [[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]]
    rx = [[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]]
    return multiply(multiply(rz, ry), rx)


def assert_matrix_close(test, actual, expected, delta=TOLERANCE):
    """Fail ``test`` unless every entry of ``actual`` is within ``delta`` of ``expected``."""
    for row_a, row_e in zip(actual, expected):
        for a, e in zip(row_a, row_e):
            test.assertAlmostEqual(a, e, delta=delta)


class MatrixTest(unittest.TestCase):
    """Products, transposes, determinants and the symmetric eigen-decomposition."""

    def test_multiply_transpose_and_determinant(self):
        a = [[1, 2, 3], [0, 1, 4], [5, 6, 0]]
        self.assertEqual(multiply(a, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]), [[1, 2, 3], [0, 1, 4], [5, 6, 0]])
        self.assertEqual(transpose(a), [[1, 0, 5], [2, 1, 6], [3, 4, 0]])
        self.assertEqual(determinant(a), 1)

    def test_eigh_reconstructs_a_symmetric_matrix(self):
        matrix = [[4.0, 1.0, -2.0], [1.0, 3.0, 0.5], [-2.0, 0.5, 5.0]]
        values, vectors = eigh_symmetric(matrix)
        diagonal = [[values[i] if i == j else 0.0 for j in range(3)] for i in range(3)]
        assert_matrix_close(self, multiply(multiply(vectors, diagonal), transpose(vectors)), matrix)
        assert_matrix_close(self, multiply(transpose(vectors), vectors), [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.assertAlmostEqual(sum(values), 12.0, delta=TOLERANCE)

    def test_eigh_of_a_diagonal_matrix_is_immediate(self):
        values, _ = eigh_symmetric([[2.0, 0, 0], [0, 7.0, 0], [0, 0, 1.0]])
        self.assertEqual(values, [2.0, 7.0, 1.0])


class EulerTest(unittest.TestCase):
    """Z-Y-X yaw, pitch and roll of rotation matrices."""

    def test_identity_is_zero(self):
        self.assertEqual(euler_zyx_deg([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0})

    def test_round_trip_of_known_angles(self):
        for angles in ((30.0, 10.0, -20.0), (-150.0, 45.0, 170.0), (90.0, -60.0, 5.0)):
            with self.subTest(angles=angles):
                result = euler_zyx_deg(zyx(*angles))
                self.assertEqual(tuple(round(result[k], 6) for k in ('yaw', 'pitch', 'roll')), angles)

    def test_enu_sensor_mounting_is_yaw_90_roll_180(self):
        result = euler_zyx_deg([[0, 1, 0], [1, 0, 0], [0, 0, -1]])  # onyx SENSOR_ENU_TO_BODY
        self.assertEqual((result['yaw'], result['pitch'], abs(result['roll'])), (90.0, 0.0, 180.0))

    def test_pitch_is_clamped_at_the_pole(self):
        self.assertEqual(euler_zyx_deg([[0, 0, 1], [0, 1, 0], [-1.0000000001, 0, 0]])['pitch'], 90.0)


class PolarRotationTest(unittest.TestCase):
    """The rotation of C = R S survives any symmetric positive scale S."""

    def test_rotation_is_recovered_from_scaled_matrix(self):
        rotation = zyx(12.0, -7.0, 3.0)
        scale = [[1.05, 0.02, -0.01], [0.02, 0.97, 0.015], [-0.01, 0.015, 1.02]]
        recovered, reflected = polar_rotation(multiply(rotation, scale))
        self.assertFalse(reflected)
        assert_matrix_close(self, recovered, rotation, 1e-12)

    def test_negative_determinant_is_flagged_and_mirrored(self):
        rotation = zyx(40.0, 0.0, 0.0)
        mirrored = [[-v for v in row] for row in multiply(rotation, [[2, 0, 0], [0, 1, 0], [0, 0, 3]])]
        recovered, reflected = polar_rotation(mirrored)
        self.assertTrue(reflected)
        assert_matrix_close(self, recovered, rotation, 1e-12)

    def test_singular_matrix_raises(self):
        with self.assertRaisesRegex(ValueError, 'singular'):
            polar_rotation([[1, 0, 0], [0, 1, 0], [0, 0, 0]])


if __name__ == '__main__':
    unittest.main()
