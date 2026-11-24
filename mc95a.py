"""Single-owner MCC172 CH0/CH1 acquisition for the local bench display."""
from collections import deque
import math
import threading
import time
from mc95a_spectrum import spectrum


def summarize(values):
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("Empty or non-finite ADC block")
    mean = sum(values) / len(values)
    return {"mean_V": mean, "rms_V": math.sqrt(sum(v*v for v in values)/len(values)),
            "ac_rms_V": math.sqrt(sum((v-mean)**2 for v in values)/len(values)),
            "peak_to_peak_V": max(values)-min(values),
            "clipping": any(abs(v) >= 4.99 for v in values)}


class MC95AReader:
    def __init__(self, address=0, factory=None, third=False):
        if third and address >= 7:
            raise ValueError("Third sensor requires a second HAT address")
        self.address = address
        self.third = third
        self.inputs = [(address, 0), (address, 1)] + ([(address+1, 0)] if third else [])
        self.channel_count = len(self.inputs)
        self.factory = factory
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.pause_requested = threading.Event()
        self.paused = threading.Event()
        self.thread = None
        self.histories = [deque(maxlen=600) for _ in range(self.channel_count)]
        self.spectral_samples = [deque(maxlen=8192) for _ in range(self.channel_count)]
        self.spectra = [None] * self.channel_count
        self.latest = [None] * self.channel_count
        self.sequence = 0
        self.total = 0
        self.error = None
        self.rate = None
        self.last_received = None
        self.epoch = time.monotonic()

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.quit.set()
        if self.thread:
            self.thread.join(timeout=4)

    def set_paused(self, paused):
        if paused:
            self.pause_requested.set()
        else:
            self.pause_requested.clear()
        return self.snapshot()

    def snapshot(self, after=None, spectrum_max_hz=None):
        with self.lock:
            age = None if self.last_received is None else time.monotonic()-self.last_received
            status = "error" if self.error else "waiting" if age is None else "stale" if age > 1 else "live"
            if self.paused.is_set():
                status = "paused" if self.pause_requested.is_set() else "resuming"
            elif self.pause_requested.is_set() and not self.error:
                status = "pausing"
            channels = [{"channel": ch, "board_address": self.inputs[ch][0],
                         "board_channel": self.inputs[ch][1],
                         "label": "S%d · HAT %d CH%d" % (ch+1, *self.inputs[ch]),
                         "latest": self.latest[ch],
                         "history": list(self.histories[ch]), "spectrum": self.spectra[ch]}
                        for ch in range(self.channel_count)]
            for channel in channels:
                history = channel['history']
                channel['history_start_sequence'] = history[0]['sequence'] if history else self.sequence + 1
                if after is not None and 0 <= after <= self.sequence:
                    channel['history'] = [point for point in history if point['sequence'] > after]
                if spectrum_max_hz is not None and channel['spectrum']:
                    original = channel['spectrum']
                    count = sum(f <= spectrum_max_hz + original['bin_Hz'] for f in original['frequency_Hz'])
                    channel['spectrum'] = dict(original,
                        frequency_Hz=original['frequency_Hz'][:count],
                        asd_V_sqrtHz=original['asd_V_sqrtHz'][:count])
            return {"status": status, "error": self.error, "age_s": age,
                    "address": self.address, "iepe": 0,
                    "pause_requested": self.pause_requested.is_set(),
                    "timing": "Shared ADC clock; separate scan starts; cross-board phase alignment unverified" if self.third else "Simultaneous channels on one HAT",
                    "sample_rate_Hz": self.rate, "sequence": self.sequence,
                    "samples_per_channel": self.total, "channels": channels,
                    "stream_id": self.epoch}

    def publish(self, channel_values, rate):
        if len(channel_values) != self.channel_count or len({len(v) for v in channel_values}) != 1:
            raise ValueError("Equally sized blocks for all configured channels are required")
        stats = [summarize(values) for values in channel_values]
        spectra = []
        for ch, values in enumerate(channel_values):
            self.spectral_samples[ch].extend(values)
            spectra.append(spectrum(list(self.spectral_samples[ch]), rate)
                           if len(self.spectral_samples[ch]) == 8192 else None)
        now = time.monotonic()
        with self.lock:
            self.sequence += 1
            self.total += len(channel_values[0])
            for ch, values in enumerate(channel_values):
                item = dict(stats[ch], t=now-self.epoch, sequence=self.sequence,
                            band_rms_V=spectra[ch]["band_rms_V"] if spectra[ch] else None)
                self.spectra[ch] = spectra[ch]
                self.latest[ch] = dict(item, waveform_V=list(values), duration_s=len(values)/rate)
                self.histories[ch].append(item)
            self.last_received = now
            self.rate = rate
            self.error = None

    def run(self):
        # Import on the Pi only; ordinary unit tests need no hardware library.
        from daqhats import mcc172, OptionFlags, SourceType
        factory = self.factory or mcc172
        while not self.quit.is_set():
            if self.pause_requested.is_set():
                # This acknowledgment is reached only after scan stop/cleanup.
                self.paused.set()
                while self.pause_requested.is_set() and not self.quit.is_set():
                    self.quit.wait(.05)
                self.paused.clear()
                continue
            hats = {}
            started = []
            try:
                specs = [(self.address, (0, 1))]
                if self.third:
                    specs.append((self.address+1, (0,)))
                for address, selected in specs:
                    hat = hats[address] = factory(address)
                    for ch in (0, 1):
                        hat.iepe_config_write(ch, 0)
                        if hat.iepe_config_read(ch) != 0:
                            raise RuntimeError("IEPE off verification failed on HAT %d" % address)
                    for ch in selected:
                        hat.a_in_sensitivity_write(ch, 1000.0)
                if self.third:
                    hats[self.address+1].a_in_clock_config_write(SourceType.SLAVE, 10240.0)
                    hats[self.address].a_in_clock_config_write(SourceType.MASTER, 10240.0)
                else:
                    hats[self.address].a_in_clock_config_write(SourceType.LOCAL, 10240.0)
                deadline = time.monotonic()+5
                while not self.quit.is_set() and not self.pause_requested.is_set():
                    clocks = [hat.a_in_clock_config_read() for hat in hats.values()]
                    rate = clocks[0][1]
                    if all(clock[2] for clock in clocks):
                        if any(abs(clock[1]-rate) > .001 for clock in clocks):
                            raise RuntimeError("HAT sample rates do not match")
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError("ADC clock sync timeout")
                    self.quit.wait(.01)
                if self.quit.is_set():
                    break
                if self.pause_requested.is_set():
                    continue
                # Never join traces across an acquisition restart.
                with self.lock:
                    for ch in range(self.channel_count):
                        self.histories[ch].clear()
                        self.spectral_samples[ch].clear()
                    self.spectra = [None] * self.channel_count
                    self.latest = [None] * self.channel_count
                    self.last_received = None
                # A shared sample clock prevents rate drift. Scan starts are
                # separate; there is no claim of common sample-zero alignment.
                for address, selected in reversed(specs):
                    hat = hats[address]
                    started.append(hat)
                    hat.a_in_scan_start(sum(1 << ch for ch in selected), 0, OptionFlags.CONTINUOUS)
                while not self.quit.is_set() and not self.pause_requested.is_set():
                    values = []
                    for address, selected in specs:
                        block = hats[address].a_in_scan_read(1024, 1)
                        if block.hardware_overrun or block.buffer_overrun:
                            raise RuntimeError("ADC overrun on HAT %d; restarting all scans" % address)
                        if len(block.data) != 1024 * len(selected):
                            raise RuntimeError("Incomplete ADC block on HAT %d" % address)
                        values.extend(block.data[i::len(selected)] for i in range(len(selected)))
                    if not self.pause_requested.is_set():
                        self.publish(values, rate)
            except Exception as exc:
                with self.lock:
                    self.error = str(exc)
            finally:
                for hat in reversed(started):
                    for operation in (hat.a_in_scan_stop, hat.a_in_scan_cleanup):
                        try:
                            operation()
                        except Exception as exc:
                            with self.lock:
                                self.error = "Could not stop ADC scan: " + str(exc)
                            self.quit.set()
            self.quit.wait(.05 if self.pause_requested.is_set() else 1)
