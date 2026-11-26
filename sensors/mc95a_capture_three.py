"""Five-second raw capture from HAT 0 CH0/CH1 and HAT 1 CH0."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
import numpy as np

if __name__ == '__main__':  # run by path: make the repository root importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sensors.mc95a import MC95AReader
from sensors.mc95a_spectrum import spectrum


class CaptureReader(MC95AReader):
    def __init__(self):
        super().__init__(third=True)
        self.raw = [[], [], []]
        self.done = threading.Event()
        self.target = None
    def publish(self, values, rate):
        if self.target is None:
            self.target = round(5*rate)
        remaining = self.target-len(self.raw[0])
        for ch in range(3):
            self.raw[ch].extend(values[ch][:remaining])
        super().publish(values, rate)
        if len(self.raw[0]) >= self.target:
            self.done.set()
            self.quit.set()


def main():
    started = datetime.now(timezone.utc)
    reader = CaptureReader()
    print('Recording S1=HAT0 CH0, S2=HAT0 CH1, S3=HAT1 CH0; IEPE OFF', flush=True)
    reader.start()
    try:
        deadline = time.monotonic()+15
        while not reader.done.wait(.2):
            if reader.snapshot()['error']:
                raise RuntimeError(reader.snapshot()['error'])
            if time.monotonic() > deadline:
                raise RuntimeError('Three-channel capture timed out')
    finally:
        reader.stop()
    state = reader.snapshot()
    if state['error']:
        raise RuntimeError(state['error'])
    root = Path.home()/'bench-data'/'mc95a'/('three_sensor_'+started.strftime('%Y%m%dT%H%M%S_%fZ'))
    root.mkdir(parents=True)
    csv_path=root/'raw.csv'
    with csv_path.open('x', newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['sample_index','time_from_own_scan_start_s','S1_H0_CH0_V','S2_H0_CH1_V','S3_H1_CH0_V'])
        writer.writerows((i,i/state['sample_rate_Hz'],*(reader.raw[ch][i] for ch in range(3))) for i in range(reader.target))
    metadata={'start_utc':started.isoformat(),'csv':str(csv_path),'samples_per_channel':reader.target,
              'sample_rate_Hz_per_channel':state['sample_rate_Hz'],'iepe':0,'timing':state['timing'],
              'identity_note':'S1/S2/S3 identify current physical ports only. Earlier A/B/C identity mapping and the identity of the sensor set aside are unconfirmed. Selected sensors are not presumed validated.',
              'analysis_note':'Discard first second for analysis; raw file retains all samples. No field calibration applied. Successful completion requires complete blocks without reported overruns.',
              'channels':[]}
    for ch, (address, port) in enumerate(reader.inputs):
        v=np.asarray(reader.raw[ch])[round(state['sample_rate_Hz']):]
        s=spectrum(v,state['sample_rate_Hz']);f=np.asarray(s['frequency_Hz']);a=np.asarray(s['asd_V_sqrtHz'])
        metadata['channels'].append({'sensor':'S'+str(ch+1),'board_address':address,'channel':port,
            'ac_rms_uV':float(np.std(v)*1e6),'band_50_1000_rms_uV':s['band_rms_V']*1e6,
            'peak_Hz':s['peak_Hz'],'clipping':bool(np.any(np.abs(v)>=4.99)),
            'tone_rms_uV':{str(hz):float(np.sqrt(np.sum(a[abs(f-hz)<=2.5]**2)*s['bin_Hz'])*1e6) for hz in (50,150)}})
    (root/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2),flush=True)


if __name__=='__main__':
    main()
