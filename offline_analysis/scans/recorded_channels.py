"""Read independent MC95A RMS levels without assigning axes or inventing AC phase.

Browser recordings retain ADC waveforms separately in JSON. Their summary
rows, also preserved by CSV cropping, carry gain-corrected RMS field in nT
and voltage in V. They are scalar port measurements, not field vectors.
"""
from __future__ import annotations

from typing import Any
import json
import math

from scans import ScanData

from offline_analysis.scans.attitude_record import AttitudeRecord, finite_list


class RecordedChannels:
    """Recognize MC95A summary columns and expose scalar plots to Offline Data."""

    @staticmethod
    def field_columns(data: ScanData) -> list[str]:
        """Known S1/S2/S3 field RMS columns, in port order (nT)."""
        return [name for k in range(1, 4)
                if (name := f'mc95a_s{k}_field_rms_nT') in data.channels]

    @classmethod
    def viewer(cls, data: ScanData, name: str, text: str = '') -> dict[str, Any] | None:
        """Scalar plots for a recording or its CSV crop; None for other files."""
        fields = cls.field_columns(data)
        if not fields:
            return None
        traces = [cls.trace(data, column) for column in fields]
        traces += [cls.trace(data, column.replace('_field_rms_nT', '_ac_rms_V'))
                   for column in fields if column.replace('_field_rms_nT', '_ac_rms_V') in data.channels]
        if name.lower().endswith('.json') and text:
            traces += cls.waveforms(text)
        return dict(sensor='electromagnetic', source=name, count=data.rows,
                    columns=fields, labels=['S1', 'S2', 'S3'],
                    scalar_traces=traces, attitude=AttitudeRecord.of_scan(data),
                    notice='MC95A independent port RMS levels. Phase and vector rotation are unavailable. '
                           'Gain and nominal sensitivity were saved during recording. '
                           'IMU receipt-time association is approximate; instruments are not synchronized.')

    @staticmethod
    def waveforms(text: str) -> list[dict[str, Any]]:
        """Received ADC blocks as independent raw traces (V); block gaps stay blank."""
        document = json.loads(text)
        if not isinstance(document, dict) or document.get('metadata', {}).get('instrument') != 'mc95a':
            return []
        traces, previous = {}, {}
        for block in document.get('waveforms', []):
            for channel in block.get('channels', []):
                label = channel.get('label', 'Unknown channel')
                values = traces.setdefault(label, [])
                if label in previous and block['sequence'] != previous[label] + 1:
                    values.append(None)
                previous[label] = block['sequence']
                values.extend(v if isinstance(v, (float, int)) and math.isfinite(v) else None
                              for v in channel.get('adc_V', []))
        return [dict(title=f'{label} raw received ADC samples', unit='V ADC', values=values)
                for label, values in traces.items()]

    @staticmethod
    def trace(data: ScanData, column: str) -> dict[str, Any]:
        """One scalar graph in nT RMS or sensor-equivalent microvolts RMS."""
        field = column.endswith('_field_rms_nT')
        port = column.split('_')[1].upper()
        values = data.column(column) * (1 if field else 1e6)
        return dict(title=f'MC95A {port} ' + ('AC field RMS' if field else 'AC voltage RMS'),
                    unit='nT RMS' if field else 'µV RMS', values=finite_list(values))
