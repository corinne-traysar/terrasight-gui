"""Fitting, applying and describing a magnetic calibration with the onyx packages.

``magnetic_calibrator`` fits onyx calibrations to onyx ``MagneticScan``
objects, ``calibration_document`` writes and reads their JSON text,
``calibrated_output`` applies them (onyx ``Scan.calibrate``) and
``calibration_angles`` describes them in degrees. All need numpy, scipy and
onyx (Python 3.12+), except ``reference``, which is pure Python so the
status endpoint works everywhere.
"""
