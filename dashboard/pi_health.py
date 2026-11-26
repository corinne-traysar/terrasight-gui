"""Cached Pi telemetry and a conservative acquisition pause guard."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import threading
import time


def read_temperature():
    return int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000


def read_throttled():
    result=subprocess.run(['vcgencmd','get_throttled'],capture_output=True,text=True,check=True,timeout=2)
    return int(result.stdout.strip().split('=',1)[1],16)


def decode_throttled(value):
    names={0:'undervoltage',1:'frequency_capped',2:'throttled',3:'soft_temperature_limit'}
    return {name:bool(value & (1 << bit)) for bit,name in names.items()} | {
        name+'_occurred':bool(value & (1 << (bit+16))) for bit,name in names.items()}


class PiHealth:
    def __init__(self,on_hot=lambda:None,temperature_reader=read_temperature,throttle_reader=read_throttled):
        self.on_hot=on_hot
        self.temperature_reader=temperature_reader
        self.throttle_reader=throttle_reader
        self.lock=threading.Lock()
        self.quit=threading.Event()
        self.thread=None
        self.temperature=None
        self.throttled=None
        self.errors=[]
        self.latched=False
        self.sampled=None
        self.last_guard=None

    def sample(self):
        errors=[]
        try:temperature=self.temperature_reader()
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            temperature=None;errors.append('Temperature unavailable: '+str(exc))
        try:throttled=self.throttle_reader()
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            throttled=None;errors.append('Throttling status unavailable: '+str(exc))
        trip=False
        with self.lock:
            self.temperature=temperature;self.throttled=throttled;self.errors=errors;self.sampled=time.monotonic()
            if temperature is not None and temperature>=75 and not self.latched:
                self.latched=True;trip=True;self.last_guard=datetime.now(timezone.utc).isoformat()
            elif temperature is not None and temperature<70:
                self.latched=False
        if trip:
            self.on_hot()
            print('Thermal guard: acquisition pause requested at %.1f C'%temperature,flush=True)

    def can_resume(self):
        with self.lock:
            return not self.latched and (self.temperature is None or self.temperature<75)

    def snapshot(self):
        with self.lock:
            return {'temperature_C':self.temperature,'throttled_hex':hex(self.throttled) if self.throttled is not None else None,
                    'flags':decode_throttled(self.throttled) if self.throttled is not None else None,
                    'errors':list(self.errors),'thermal_guard_active':self.latched,'last_guard_utc':self.last_guard,
                    'pause_threshold_C':75,'resume_below_C':70,
                    'age_s':None if self.sampled is None else time.monotonic()-self.sampled}

    def start(self):
        def run():
            while not self.quit.is_set():
                self.sample();self.quit.wait(3)
        self.thread=threading.Thread(target=run,daemon=True,name='pi-health');self.thread.start()

    def stop(self):
        self.quit.set()
        if self.thread:self.thread.join(timeout=3)
