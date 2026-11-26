"""Unified Terrasight bench dashboard: one server for every instrument view.

Serves the Overview, VN-100, MC95A, AP230, Calibration and Offline Data pages
and their JSON APIs on one port (requests are answered by ``bench_handler``).
Every instrument starts stopped and has its own start/stop control; the Pi
health guard stops them all when the Pi runs hot.
"""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

if __name__ == '__main__':  # run by path: make the repository root importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.bench_handler import BenchHandler
from dashboard.vn100_control import BenchMeasurements, VNControl
from sensors.ap230 import AP230Reader, DEFAULT_DEVICE as AP230_DEVICE
from sensors.mc95a import MC95AReader
from dashboard.pi_health import PiHealth

DEFAULT_DEVICE='/dev/serial/by-id/usb-FTDI_USB-RS232-WE_AV0LSPFW-if00-port0'


def make_bench_server(host,port,measurements,mc,health,vn,ap=None):
    """A bench dashboard server on ``host``:``port``; ``ap`` defaults to an unstarted AP230 reader."""
    return ThreadingHTTPServer((host,port),partial(BenchHandler,measurements=measurements,mc=mc,health=health,vn=vn,ap=ap if ap is not None else AP230Reader()))


def main():
    """Run the dashboard with every instrument stopped until it is started from the browser."""
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8000)
    p.add_argument('--device',default=DEFAULT_DEVICE);p.add_argument('--third',action='store_true')
    p.add_argument('--ap230-device',default=AP230_DEVICE)
    args=p.parse_args()
    measurements=BenchMeasurements(recording_directory=Path.home()/'terrasight-bench'/'captures')
    measurements.connection(False,'VN-100 acquisition stopped')
    mc=MC95AReader(third=args.third);mc.set_paused(True)
    vn=VNControl(args.device,measurements)
    ap=AP230Reader(args.ap230_device)
    def pause_all():mc.set_paused(True);vn.stop();ap.stop()
    health=PiHealth(on_hot=pause_all)
    server=make_bench_server(args.host,args.port,measurements,mc,health,vn,ap)
    mc.start();health.start()
    print(f'Terrasight Bench: http://mypi.local:{args.port} — acquisition starts stopped',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:print('Stopping unified bench dashboard',flush=True)
    finally:server.server_close();health.stop();mc.stop();vn.stop();ap.stop()


if __name__=='__main__':main()
