# Terrasight GUI

A Raspberry Pi bench dashboard with Overview, VN-100, MC95A, AP230, and Connect to Pi views. The live dashboard runs in `bench_app.py` on port 8000. A local read-only preview serves the same browser files and forwards telemetry to the Pi. Standalone sensor entry points remain available for bench work.

## Private Tailscale Connection

Connect the Mac and Pi to the same authorized tailnet. Use the Pi's actual Tailscale IPv4 address or MagicDNS name; `mypi.local` is the LAN fallback and does not select Tailscale. Existing tailnet access rules must permit the dashboard port and SSH. See [Tailscale server connections](https://tailscale.com/docs/how-to/set-up-servers).

Copy `connection.example.json` to `connection.local.json` and set `pi_url` to `http://<pi-tailscale-host>:8000` and `ssh_target` to `<pi-user>@<pi-tailscale-host>`. This ignored file stays on the machine using it. Environment variables `TERRASIGHT_PI_URL` and `TERRASIGHT_SSH_TARGET` override the file. Without an SSH target, the connection panel uses the dashboard hostname and the SSH client's configured user. No password, SSH private key, or Tailscale auth key belongs in these settings.

Start the live dashboard in the Pi's existing environment:

```bash
~/venvs/mcc172/bin/python ~/terrasight-gui/bench_app.py --third
```

To restrict its listener to the Pi's Tailscale IPv4 interface, add `--host <pi-tailscale-ip>`. Use the direct HTTP URL over Tailscale for live acquisition controls. The current origin checks expect HTTP. HTTPS reverse-proxy controls are not configured by this setup.

On the Mac, start the local view:

```bash
python3 scripts/preview_theme.py
```

Open `http://127.0.0.1:8766/`. `--pi-url http://<pi-tailscale-host>:8000` overrides the configured preview target. This listener remains on loopback, and acquisition commands are blocked. Use the live Pi URL for controls. The Connect to Pi panel and `Connect to Terrasight.command` use local SSH settings; the launcher joins the existing shared tmux session and does not start acquisition. Preview failures show unavailable telemetry.

The repository contains application code and tests. `connection.local.json`, credentials, captures, bench records, generated outputs, and machine-specific SD-card recovery utilities are excluded. Existing local files are preserved. No public hosting or Tailscale Funnel is configured.

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

Select **Start Recording** while the sensor is live. Select **Stop Recording** to flush and close the file. The GUI shows the full Pi path and row count. Files default to `~/terrasight-bench/captures/vn100-<UTC timestamp>-<unique suffix>.csv` for the bench account; override the directory with `--recording-dir`. Each start creates a new file without overwriting earlier captures.

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

Keep captures and credentials outside Git. The current bench captures live separately on the Pi at `~/terrasight-bench/captures/`. New recordings are saved alongside earlier captures with unique filenames; existing captures are never overwritten. Connection details and approved bench results are maintained in Notion.

## MC95A Live Voltage Monitor

The MC95A has a separate small monitor in the same checkout. Run it on the Pi with the MCC library installed; it can run alongside the VN-100 app on port 8000. Stop other MCC172 readers first: one process must own the HAT.

```bash
~/venvs/mcc172/bin/python ~/terrasight-gui/mc95a_app.py
```

Open `http://mypi.local:8001`. The monitor continuously acquires CH0 and CH1 simultaneously at 10,240 samples/s per channel from board address 0 and explicitly disables/verifies IEPE on both channels. `--address` selects another board. It shows both channels’ latest 1,024-sample voltage waveforms, 100 ms AC RMS (block mean removed), peak-to-peak voltage, mean voltage, and up to 60 seconds of RMS history. Values use microvolts; no magnetic-field calibration is applied. Waveforms are consecutive hardware samples; history timestamps are Pi block-receipt times. Display polling is independent of acquisition, so browsers may skip blocks. Overruns/incomplete blocks are reported and restart acquisition with a new history; stale data is hidden. Pause Plots freezes only the browser plots, with numeric acquisition continuing. Closing the browser does not stop acquisition; Ctrl+C in the shared Pi terminal stops the server and ADC scan.

This monitor does not save raw recordings. Earlier finite captures remain under `~/bench-data/mc95a/`. Acquisition readiness does not establish sensor response or field accuracy.

### Magnetic Field and Spectrum

The MC95A monitor additionally requires NumPy in its Python environment (`~/venvs/mcc172/bin/pip install numpy`). An independent 8,192-sample rolling buffer per channel (0.8 seconds at 10.24 kS/s) produces a mean-removed, Hann-windowed, one-sided power spectral density, updated every 100 ms. The spectrum shows voltage amplitude spectral density in µV/√Hz, 1.25 Hz bin spacing, and the largest bin within 10–3,000 Hz. This peak may be noise; it is not a validated source frequency. Range selection changes only the plot.

Estimated AC Magnetic Field integrates the voltage PSD over approximately 50–1,000 Hz (one 1.25 Hz guard bin at each edge retains the Hann main lobe of a tone exactly on the boundary) and divides its RMS voltage by a flat sensitivity. The default manufacturer nominal 1 mV/mG gives 100 nT per mV (100,000 nT per V). The browser sensitivity input can substitute a certificate value in mV/mG; it is display-only, is saved per browser origin, and does not apply frequency-dependent calibration or phase reconstruction. Estimates include system noise and motion artifacts; no static field, vector, or instantaneous magnetic-field waveform is inferred. The field trend uses overlapping 0.8-second windows, and resets across acquisition restarts.

### Compare Two MC95As

The monitor acquires CH0 and CH1 of one MCC172 simultaneously (channel mask 3) at 10,240 samples/s **per channel**, with IEPE explicitly disabled and verified on both. Connect both sensors to the selected board (default address 0). An installed second HAT is unused by this monitor; it must have a different hardware address. No cross-board synchronization is claimed.

All four plots overlay CH0 in green and CH1 in amber, with per-channel voltage, field and peak-frequency readouts. Each channel has an independent spectral buffer, history, and sensitivity input. Channel visibility controls affect only the plots. The sample count is per channel. Keep the sensors parallel and close together for a first comparison, then vary one sensor’s orientation or distance. Similarity of the signals is a bench check, not a presumed result; each input also records electronics noise, including when no sensor is connected.

### Pause Acquisition for a Signal-Cable Swap

**Pause Acquisition** requests a hardware scan stop on both CH0 and CH1. Wait for **Acquisition Paused** before changing signal connections. That status is acknowledged only after scan stop and cleanup return successfully; a stop failure reports an error rather than a paused state. The server and browser stay available, and the sample counter stops. **Resume Acquisition** reinitializes the HAT, verifies IEPE off on both channels, and starts a new scan with cleared spectral buffers and plot history. Controls are shared across browsers and require the same GUI origin. **Pause Plots** continues to freeze only the browser display and does not stop acquisition. Pausing acquisition does not power down the Pi; changes to HAT stacking or address jumpers still require shutdown and disconnected power.

### Three Sensors Across Two HATs

Use `mc95a_app.py --third` for S1 = HAT 0 CH0, S2 = HAT 0 CH1, S3 = HAT 1 CH0 (or the selected `--address` and next address). `--start-paused` opens the GUI without starting acquisition. All configured inputs are stopped before Pause is acknowledged. IEPE is disabled/verified on both inputs of both boards, including the unused fourth input. HAT 1 uses the shared slave ADC clock, configured before HAT 0 starts the master clock. Rates and clock synchronization flags are checked. Each board starts a separate continuous scan; sample-zero and cross-board phase alignment are not established without a common trigger. Voltage windows and spectra can be compared, but cross-board phase or propagation delay must not be inferred. An error/overrun on either board restarts the whole acquisition with cleared history.

With the GUI process stopped, `~/venvs/mcc172/bin/python ~/terrasight-gui/mc95a_capture_three.py` saves a complete five-second raw three-input capture and labeled metadata under `~/bench-data/mc95a/three_sensor_<UTC>/`. The CSV retains all samples; spectral summaries discard the first second. S1/S2/S3 are port labels rather than serial-number identities or declarations of sensor health.

## Unified Bench Dashboard

Run `~/venvs/mcc172/bin/python ~/terrasight-gui/bench_app.py --third` in the Pi's shared terminal, then open `http://mypi.local:8000/`. All instruments start stopped. Overview, VN-100, MC95A and Connect to Pi share one server. The existing VN-100 pose/plots/CSV recording and the MC95A plots remain available as instrument tabs. Start/Stop VN-100 controls its serial reader; MC95A Pause/Resume controls all configured ADC scans. The default VN-100 serial path is the previously used FTDI by-id path; override it with `--device` if the adapter changes. An unplugged VN-100 does not block the rest of the dashboard. Co-display does not establish VN-100/MCC172 time alignment.

Pi health samples CPU temperature and firmware voltage/throttling flags every three seconds, independent of the browser. At 75°C it requests MC95A pause and stops VN-100 reception/recording; restart controls remain blocked until temperature drops below 70°C. Acquisition remains stopped after cooling until manually resumed. Current flags are distinguished from earlier-this-boot flags. Missing telemetry is shown as unknown, not interpreted as healthy. This is a conservative acquisition-load guard, not physical cooling or a guarantee against overheating; retain the Pi's built-in thermal protections and use adequate airflow/active cooling. No fan settings or firmware/kernel settings are changed.

Connect to Pi provides a Terminal SSH link and copy buttons for the combined SSH/tmux join command, dashboard startup and shutdown commands. Passwords stay in Terminal. The local Mac file `Connect to Terrasight.command` can be double-clicked to open the same shared session; it contains no password. The browser cannot display this connection panel until the Pi's dashboard server is running, so retain the local launcher or the command for bootstrapping after shutdown. The standalone VN-100 and MC95A entry points remain available; do not run standalone readers alongside the unified server on the same hardware.

### AP230 Live View

The unified dashboard includes an AP230 tab at `http://mypi.local:8000/ap230`. Connect the supplied APS interface box to a Pi USB port; the default stable device path identifies interface serial AP0D3YPD. Override it with `--ap230-device` if needed. Start AP230 opens the port at 9600 baud and requests Auto-Send if no valid readings arrive. Pause Acquisition sends Stop and closes the port. The thermal guard stops AP230 along with the other readers.

X/Y/Z and total-field values are shown in microtesla (ASCII Gauss values multiplied by 100), with 15/30/60-second history and Freeze Plots. History is held in memory; no continuous recording is started by this view. Restarting acquisition clears history. Stale or disconnected values are hidden; Pi receipt times do not establish sensor timing or synchronization. Do not run a separate AP230 capture/reader while the GUI owns the port.

### MC95A Display Refresh

The MC95A detail view targets one request every 100 ms, including transfer and drawing time. It requests only new history points and the spectrum bins needed for the selected frequency range; gzip reduces transfer size. The browser retains the 60-second history and clears prior data when the acquisition history or server restarts. Waveform samples, ADC acquisition rate, spectral analysis and field calculations are unchanged. The configuration line shows the achieved rate of fresh display updates over the last five seconds. Actual refresh depends on the network, selected spectrum range and browser load.

Display regression checks: `python3 -m unittest discover -s tests -p test_mc95a_display.py` and `node tests/mc95a_display.cjs`.

### Shared Instrument Views

Overview and its MC95A/AP230 instrument iframes use one compressed incremental telemetry feed targeting 10 display updates/s. VN-100 Overview and detail share one continuous event stream targeting 20 display updates/s, retained when switching pages. Existing history seeds each newly opened detail view. Health updates do not overwrite instrument badges. Gain and MC95A sensitivity settings are saved per browser origin and shared immediately across instrument views and other tabs on that origin. The local read-only preview and live Pi serve the same page files; use the live Pi URL for acquisition controls and one consistent settings origin. Display sharing does not establish hardware time synchronization.

The preview requests compressed telemetry, resolves the Pi hostname once, and caches distinct query cursors separately. Both preview and Pi require a page reload after a frontend update. Regression checks include `node tests/telemetry.cjs` and `node tests/overview.cjs`.
