"""Turn a file the browser sent (name and text) into an onyx scan.

onyx's readers parse the text by file name (``.json`` or delimited text; see
onyx ``scans.files``) into a ``ScanTable``. ``ImuAttitude`` then adds
yaw/pitch/roll columns when the file has only raw IMU readings. The table is
wrapped as generic onyx ``ScanData`` (loading and cropping any file) or as the
sensor's own scan class, chosen by the view: ``magnetic`` is onyx
``MagneticScan``, ``electromagnetic`` is onyx ``ElectromagneticScan``.
"""
from __future__ import annotations

from typing import Optional

from scans import ElectromagneticScan, MagneticScan, Scan, ScanData, ScanTable
from scans.files.scan_readers import ScanReader

from offline_analysis.imu.imu_attitude import ImuAttitude

SENSORS: dict[str, type[Scan]] = {'magnetic': MagneticScan, 'electromagnetic': ElectromagneticScan}


class ScanLoader:
    """Reads scan files with onyx and derives missing IMU angles."""

    def __init__(self, attitude: Optional[ImuAttitude] = None):
        """Derive angles with ``attitude`` (a default ImuAttitude when None)."""
        self.attitude = attitude or ImuAttitude()

    def table(self, name: str, text: str) -> ScanTable:
        """The columns of the file ``name`` with contents ``text``, plus derived angles.

        Raises:
            ValueError: if the file has no rows or no numeric column, or is invalid.
        """
        return self.attitude.augment(ScanReader.for_name(name).read(text))

    def data(self, name: str, text: str) -> ScanData:
        """The file as generic onyx ``ScanData`` (any columns, no sensor meaning)."""
        table = self.table(name, text)
        return ScanData(table.columns, table.axis, table.metadata)

    def sensor_scan(self, sensor: str, name: str, text: str) -> Scan:
        """The file as the onyx scan class of ``sensor`` ('magnetic' or 'electromagnetic').

        Raises:
            ValueError: on an unknown sensor or a file without that sensor's columns.
        """
        return self.as_sensor(sensor, self.table(name, text))

    @staticmethod
    def as_sensor(sensor: str, source: ScanData | ScanTable) -> Scan:
        """``source`` (data or a table) wrapped as the onyx scan class of ``sensor``."""
        if sensor not in SENSORS:
            raise ValueError(f'unknown sensor {sensor!r}; choose magnetic or electromagnetic')
        table = source.table if isinstance(source, ScanData) else source
        return SENSORS[sensor].from_table(table)

    @staticmethod
    def magnetic(source: ScanData | ScanTable) -> MagneticScan:
        """``source`` as an onyx ``MagneticScan``; ValueError without field columns."""
        return MagneticScan.from_table(source.table if isinstance(source, ScanData) else source)


LOADER = ScanLoader()
"""The loader the web API uses."""
