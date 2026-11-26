"""The dashboard's view of scan files, built on the onyx ``scans`` package.

onyx reads the files (CSV/TSV/text/JSON), holds the columns (``ScanData``,
``MagneticScan``, ``ElectromagneticScan``), crops and calibrates them. This
package adds what only the browser views need: ``scan_loader`` (file text to
an onyx scan, with yaw/pitch/roll derived from a raw IMU), ``scan_window``
(the crop window and channel selection), ``channel_profiles`` (pre-selected
channels per sensor type), ``attitude_record`` (angles in degrees for the
plots) and ``viewer_data`` (Offline Data vectors in nT). Needs numpy and onyx
(Python 3.12+).
"""
