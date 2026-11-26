"""Offline scan analysis for the dashboard's Calibration and Offline Data views.

Ported from Simulation-Examples (``calibration_crop``, ``sensor_viewer`` and
``sensor_calibration``). ``scans`` loads files, detects channels and crops,
using only the standard library, so it runs on the Pi. ``magnetic_calibration``
fits and applies a magnetic calibration and needs numpy and the onyx
``calibration`` package (Python 3.12+); ``web_api`` serves both as JSON and
reports when fitting is unavailable instead of failing to import.
"""
