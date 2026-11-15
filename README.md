# Terrasight GUI

A small bench-test application: the Raspberry Pi reads and decodes VN-100 serial messages, and a browser on a computer displays the measurements over Ethernet or Wi-Fi.

## Run on the Pi

Python 3.9+ on Raspberry Pi OS; no third-party packages or frontend build required. The user must have serial-port access (normally membership in `dialout`). Stop other serial readers before starting this application.

```bash
python3 app.py --device /dev/serial/by-id/usb-FTDI_USB-RS232-WE_AV0LSPFW-if00-port0
```

Open `http://mypi.local:8000` in the computer's browser, or substitute the Pi's IP address. Both devices must have network connectivity to each other; the application is the same over Ethernet or Wi-Fi. It binds to the Pi's network interfaces for this trusted local bench network. It has no login or remote sensor-control endpoints.

Press Ctrl+C in the Pi terminal to stop. The application retries the stable serial path after disconnects. Reloading or closing a browser does not restart the reader. Multiple browser tabs share the same acquisition process.

## First Milestone

- Live values and plots for attitude, magnetic field, acceleration, and angular rate.
- A schematic 3D sensor pose driven by reported yaw/pitch/roll, with sensor XYZ axes and a fixed NED reference. Stale poses are dimmed and labeled as historical. It shows orientation, not position or translation.
- Live, waiting, stale, disconnected, and Pi-unreachable states.
- A 60-second browser history, capped at 2,400 samples. The Pi also retains at most 2,400 samples. This is display history, not a lossless recording.
- Serial input is validated before use. No sensor configuration commands are transmitted.

VNYMR fields follow VectorNav UM001, section “Yaw, Pitch, Roll, Magnetic, Acceleration, and Angular Rates”: yaw/pitch/roll in degrees; magnetic XYZ in gauss; acceleration XYZ in m/s²; angular-rate XYZ in rad/s. These are compensated measurements and calculated attitude, not unprocessed internal MEMS readings. [VectorNav manual](https://www.eol.ucar.edu/sites/default/files/files_live/private/VN100manual.pdf).

Timestamps are Pi receive times, not sensor sample timestamps. Several packets can arrive in one serial read, so their receive times may match. A continuous server-sent event connection sends batches up to 20 times per second; acquisition processes every received valid VNYMR packet independently. Drawing follows the browser's animation frames. Plot axes expand for new extremes and stay stable for the session; reloading resets their ranges. Plot gaps mark missing sequences or receive-time gaps over one second. Units and values are passed through without conversion or smoothing.

## Code Organization

| Module | Responsibility |
| --- | --- |
| `vn100.py` | Serial connection, framing, checksum validation, decoding, retry, bounded measurement store |
| `app.py` | One HTTP application serving the browser and measurement snapshots |
| `web/` | Browser-only values, plots, and connection status |
| `tests/` | Real captured packet fixture, stream framing, state, HTTP delivery, and serial reconnection |

`VN100Reader` owns the serial file descriptor and writes decoded samples to `Measurements`. `/api/events` streams measurement batches using a sequence cursor; `/api/samples?after=N` remains available for diagnostics. The stream disables TCP buffering delays and the browser reconnects automatically. There is no database, generic sensor framework, or separate deployment. Other sensors and recording controls will be added in later steps when their requirements are known.

## Test

```bash
python3 -m unittest discover -s tests -v
```

The browser cadence regression check requires Node.js for development only:

```bash
node tests/browser_timing.cjs
node tests/pose.cjs
```

It runs the actual browser code with a deterministic 40 Hz input and verifies that displayed values update at least 15 times per second, with no healthy-input gap above 100 ms. The original request/response polling loop fails with a 200 ms gap even before network latency is added.

`pose.cjs` checks the right-handed body-to-NED 3-2-1 rotation: positive yaw turns +X toward +Y, positive pitch turns +X toward -Z, and positive roll turns +Y toward +Z. The canvas renderer uses that matrix directly, with no additional attitude filtering. Physical axis correspondence still requires a controlled movement check against the sensor's markings and any configured reference-frame rotation.

The tests use pseudo-terminals to check fragmentation and device replacement without touching the physical sensor. Physical movement response, accuracy, Ethernet connectivity, and combined-sensor operation require separate bench checks.

## Data and Credentials

Keep captures and credentials outside Git. The current bench captures live separately on the Pi at `/home/corinne/terrasight-bench/captures/`. This version does not create recordings or overwrite those captures. Connection details and approved bench results are maintained in Notion.
