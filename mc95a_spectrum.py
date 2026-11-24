"""Hann-windowed one-sided voltage PSD and nominal AC field estimate."""
import numpy as np


def spectrum(values, rate):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 8 or not np.all(np.isfinite(x)) or not np.isfinite(rate) or rate <= 0:
        raise ValueError("Invalid spectrum input")
    window = np.hanning(len(x))
    transform = np.fft.rfft((x-x.mean())*window)
    psd = abs(transform)**2 / (rate * np.sum(window**2))
    psd[1:-1 if len(x) % 2 == 0 else None] *= 2
    frequencies = np.fft.rfftfreq(len(x), 1/rate)
    spacing = rate/len(x)
    # One guard bin retains a Hann-windowed tone exactly at 50 or 1000 Hz.
    # The displayed band is approximate to the 1.25 Hz FFT bin spacing.
    band = (frequencies >= 50-spacing) & (frequencies <= 1000+spacing)
    band_rms = float(np.sqrt(np.sum(psd[band]) * spacing))
    candidates = np.flatnonzero((frequencies >= 10) & (frequencies <= 3000))
    peak = int(candidates[np.argmax(psd[candidates])]) if len(candidates) and np.max(psd[candidates]) > 0 else None
    return {"bin_Hz": spacing, "window_s": len(x)/rate,
            "frequency_Hz": frequencies.tolist(),
            "asd_V_sqrtHz": np.sqrt(psd).tolist(),
            "band_rms_V": band_rms,
            "peak_Hz": float(frequencies[peak]) if peak is not None else None}


def nominal_field_nT(voltage_rms, sensitivity_mV_per_mG=1.0):
    if not np.isfinite(sensitivity_mV_per_mG) or sensitivity_mV_per_mG <= 0:
        raise ValueError("Sensitivity must be positive")
    # 1 mG = 100 nT; 1 mV = .001 V.
    return voltage_rms * 100000 / sensitivity_mV_per_mG
