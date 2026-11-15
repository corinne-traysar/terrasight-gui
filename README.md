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
- Start/Stop Recording saves validated samples to CSV on the Pi while the display continues.
- A 60-second browser history, capped at 2,400 samples. The Pi also retains at most 2,400 samples. This is display history, not a lossless recording.
- Serial input is validated before use. No sensor configuration commands are transmitted.

VNYMR fields follow VectorNav UM001, section “Yaw, Pitch, Roll, Magnetic, Acceleration, and Angular Rates”: yaw/pitch/roll in degrees; magnetic XYZ in gauss; acceleration XYZ in m/s²; angular-rate XYZ in rad/s. These are compensated measurements and calculated attitude, not unprocessed internal MEMS readings. [VectorNav manual](https://www.eol.ucar.edu/sites/default/files/files_live/private/VN100manual.pdf).

Timestamps are Pi receive times, not sensor sample timestamps. Several packets can arrive in one serial read, so their receive times may match. A continuous server-sent event connection sends batches up to 20 times per second; acquisition processes every received valid VNYMR packet independently. Drawing follows the browser's animation frames. Plot axes expand for new extremes and stay stable for the session; reloading resets their ranges. Plot gaps mark missing sequences or receive-time gaps over one second. Units and values are passed through without conversion or smoothing.

## Align the View

Place the VN-100 flat with its connector toward you and select **Align View**. The camera moves around the vertical axis to face the connector at the current sensor heading. Live pitch, roll, and subsequent yaw remain visible; the NED compass follows the camera viewpoint. This changes only the browser camera, never sensor configuration, measurements, or plots. **Reset View** restores the default camera. Alignment lasts until page reload and is available only with live attitude data.

## Record CSV on the Pi

Select **Start Recording** while the sensor is live. Select **Stop Recording** to flush and close the file. The GUI shows the full Pi path and row count. Files default to `/home/corinne/terrasight-bench/captures/vn100-<UTC timestamp>-<unique suffix>.csv` for the bench account; override the directory with `--recording-dir`. Each start creates a new file without overwriting earlier captures.

CSV includes UTC Pi receipt time, receipt milliseconds since Unix epoch, acquisition sequence, and all 12 VNYMR measurements with units in the column names. Every validated sample is recorded, independent of the bounded plot history and browser update rate. These are Pi receipt timestamps, not sensor timestamps. Alignment affects only the camera.

Recording is shared across browser tabs and continues through page reload/closure. Sensor disconnection leaves the recording open, adds no artificial rows, and resumes into the same file after reconnection; sequence and receipt times reveal gaps. Stop remains available during a sensor gap. If the Pi is unreachable, the browser marks recording status unknown. File errors stop recording and are displayed while live acquisition continues. Output is flushed every half second, synced to disk on Stop, and closed on normal application shutdown; abrupt power loss can lose recent buffered data. Repeated start/stop commands are safe and do not create duplicate active files.

## Code Organization

| Module | Responsibility |
| --- | --- |
| `vn100.py` | Serial connection, framing, checksum validation, decoding, retry, bounded measurement store |
| `recording.py` | CSV file lifecycle, headers, sample writes, and file errors |
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

`pose.cjs` checks the right-handed body-to-NED 3-2-1 rotation: positive yaw turns +X toward +Y, positive pitch turns +X toward -Z, and positive roll turns +Y toward +Z. It also verifies that screen-right cross screen-up points toward the camera and that positive NED yaw projects clockwise from above the table. A reversed camera basis originally mirrored yaw and roll; correcting the camera removes that reflection without per-axis sign changes. The temporary roll-only correction was removed. Received measurements, numeric readouts, and plots retain their original signs; no attitude filtering is added. Physical confirmation remains a bench check.

The illustrative rugged housing follows the supplied product image: red chamfered casing, silver mounting tabs, black connector and gold contacts. Connector placement on -X and the side tabs follow VectorNav's [public mechanical drawing](https://www.vectornav.com/docs/default-source/mechanical-drawings/vn-100-cr-asm_v7.0.0.pdf). The supplied image is included unchanged in the expandable Housing Reference. The model is a visual aid, not a dimensional CAD model.

The tests use pseudo-terminals to check fragmentation and device replacement without touching the physical sensor. Physical movement response, accuracy, Ethernet connectivity, and combined-sensor operation require separate bench checks.

## Data and Credentials

Keep captures and credentials outside Git. The current bench captures live separately on the Pi at `/home/corinne/terrasight-bench/captures/`. New recordings are saved alongside earlier captures with unique filenames; existing captures are never overwritten. Connection details and approved bench results are maintained in Notion.
