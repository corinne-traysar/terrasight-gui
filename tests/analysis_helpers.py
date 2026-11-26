"""Small scan files for the analysis tests (Calibration and Offline Data views)."""
import json

MAG_HEADER = ['time [s]', 'Bx [nT]', 'By [nT]', 'Bz [nT]', 'acc_x', 'gyro_z', 'yaw', 'temperature_C']
MAG_B = ('Bx [nT]', 'By [nT]', 'Bz [nT]')
MAG_IMU = ('acc_x', 'gyro_z', 'yaw')
# Header of recording.py: the Pi's VN-100 CSV recordings.
VN100_HEADER = ['received_utc', 'received_ms', 'sequence', 'yaw_deg', 'pitch_deg', 'roll_deg',
                'magnetic_x_gauss', 'magnetic_y_gauss', 'magnetic_z_gauss',
                'acceleration_x_m_s2', 'acceleration_y_m_s2', 'acceleration_z_m_s2',
                'angular_rate_x_rad_s', 'angular_rate_y_rad_s', 'angular_rate_z_rad_s']


def text_scan(header, rows, delimiter=','):
    """A header line and rows joined by ``delimiter``, as file text."""
    lines = [delimiter.join(header)] + [delimiter.join(str(v) for v in row) for row in rows]
    return '\n'.join(lines) + '\n'


def mag_rows(count=11):
    """Rows of MAG_HEADER at time 0..count-1 s: Bx = 100 t, By = -t, the rest constant."""
    return [[t, 100.0 * t, -t, 5.0, 9.8, 0.1 * t, 2.0 * t, 25.0] for t in range(count)]


def mag_scan():
    """The default 11-row magnetic scan as CSV text."""
    return text_scan(MAG_HEADER, mag_rows())


def vn100_scan(count=4):
    """A VN-100 recording: 0.5 s apart, field (0.2, -0.1, 0.4) gauss, yaw 10 t degrees."""
    rows = [[f'2026-11-24T10:00:{i // 2:02d}.{5 * (i % 2)}00+00:00', 1795255200000 + 500 * i, i + 1,
             10.0 * i, 1.0, -2.0, 0.2, -0.1, 0.4, 0.0, 0.0, -9.81, 0.0, 0.0, 0.01]
            for i in range(count)]
    return text_scan(VN100_HEADER, rows)


def em_json(count=5):
    """A scan shaped like the bunker cable output: samples with nested phasors.

    Row i is at distance 10 i m with field_T real = [i, 2i, 3i], imag = [-i, 0, 0].
    """
    samples = [dict(source_index=i, distance_m=10.0 * i, position_m=[0, 0, -i],
                    field_T=dict(real=[i, 2 * i, 3 * i], imag=[-i, 0, 0]), strength_T=[i, i, i],
                    theta_rad=[0, 0, 0], valid=True)
               for i in range(count)]
    return json.dumps(dict(status='completed', samples=samples))


EARTH_T = [0.0, 3.0e-5, -4.0e-5]  # |Earth| = 5e-5 T = 50 000 nT


def mag_json(anomalies_t):
    """A bunker-panel-like output: combined = Earth + anomaly per sample, east/north/up."""
    samples = [dict(source_index=i, distance_m=float(i), position_m=[0, 0, -i], earth_field_T=EARTH_T,
                    anomaly_field_T=a, combined_field_T=[e + d for e, d in zip(EARTH_T, a)])
               for i, a in enumerate(anomalies_t)]
    return json.dumps(dict(coordinate_frame='east_north_up', samples=samples))


def phasor_json(phasors_t):
    """A bunker-cable-like output with field_T real/imag per sample, east/north/up."""
    samples = [dict(source_index=i, distance_m=float(i), field_T=dict(real=re, imag=im))
               for i, (re, im) in enumerate(phasors_t)]
    return json.dumps(dict(coordinate_frame='east_north_up', samples=samples))
