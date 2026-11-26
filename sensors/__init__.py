"""Sensor acquisition that runs on the Pi: VN-100, AP230 and MC95A readers.

Each reader owns its device (serial port or MCC172 HATs) and keeps a bounded
store of validated samples; ``recording`` writes VN-100 samples to CSV. The
``*_capture*`` modules are standalone finite-capture command-line tools.
"""
