"""Tests of imu/attitude_sources.py: yaw/pitch/roll from a gyroscope or an accelerometer."""
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402

from imu_helpers import G, tilted_force  # noqa: E402
from offline_analysis.imu.attitude_sources import (AccelerometerAttitude, AttitudeSource,  # noqa: E402
                                                   GyroscopeAttitude, ImuReadings)


def level_turn(count=11, yaw_rate=0.1):
    """Readings of a level IMU at rest turning about down at ``yaw_rate`` rad/s, 1 s apart."""
    force = np.tile([0.0, 0.0, -G], (count, 1))
    rate = np.tile([0.0, 0.0, yaw_rate], (count, 1))
    return ImuReadings(force, rate, np.arange(count, dtype=float))


class BestForTest(unittest.TestCase):
    """The gyroscope is used only with rates and a time axis."""

    def test_choice(self):
        readings = level_turn()
        self.assertIsInstance(AttitudeSource.best_for(readings), GyroscopeAttitude)
        self.assertIsInstance(AttitudeSource.best_for(ImuReadings(readings.force_m_s2)), AccelerometerAttitude)
        no_time = ImuReadings(readings.force_m_s2, readings.rate_rad_s, None)
        self.assertIsInstance(AttitudeSource.best_for(no_time), AccelerometerAttitude)


class GyroscopeAttitudeTest(unittest.TestCase):
    """Strapdown integration through onyx navigation."""

    def test_constant_yaw_rate_integrates_to_rate_times_time(self):
        # 0.1 rad/s about down for 10 s -> yaw 1.0 rad; level, so pitch = roll = 0.
        angles = GyroscopeAttitude().angles_rad(level_turn())
        self.assertAlmostEqual(angles[-1, 0], 1.0, delta=1e-9)
        self.assertAlmostEqual(float(np.abs(angles[:, 1:]).max()), 0.0, delta=1e-9)

    def test_without_rates_raises(self):
        with self.assertRaisesRegex(ValueError, 'angular rates'):
            GyroscopeAttitude().angles_rad(ImuReadings(np.tile([0.0, 0.0, -G], (3, 1))))


class AccelerometerAttitudeTest(unittest.TestCase):
    """Per-row tilt from gravity; yaw is 0."""

    def test_pitch_and_roll_from_gravity(self):
        force = np.array([tilted_force(0.3, -0.4), tilted_force(0.0, 0.0)])
        angles = AccelerometerAttitude().angles_rad(ImuReadings(force))
        np.testing.assert_allclose(angles, [[0.0, 0.3, -0.4], [0.0, 0.0, 0.0]], atol=1e-12)

    def test_sources_explain_their_yaw(self):
        self.assertIn('0', AccelerometerAttitude.yaw)
        self.assertIn('first row', GyroscopeAttitude.yaw)


if __name__ == '__main__':
    unittest.main()
