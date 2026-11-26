"""Group scan columns into 3-axis vectors and find a sensor's B vector among them.

A column belongs to a vector when its name holds an axis token (x/y/z, e/n/u,
east/north/up or 0/1/2); the name with that token replaced by ``*`` is the
vector's key: ``field_T_real_0`` -> ``field_t_real_*``, ``Bx_re`` -> ``b*_re``.
"""
from __future__ import annotations

import re
from typing import Tuple

from offline_analysis.scans.channels import normalize

AXES = {'x': 0, 'e': 0, 'east': 0, '0': 0, 'y': 1, 'n': 1, 'north': 1, '1': 1,
        'z': 2, 'u': 2, 'up': 2, '2': 2}
_ATTACHED = re.compile(r'^(b|h|mag|em)(x|y|z)$')
_MAGNETIC = re.compile(r'^(combined_)?(b|mag|magnetic|magnetometer|b_?field|field(_t|_nt|_ut)?)'
                       r'[_.\- ]*\*([_.\- ]*(t|nt|ut|gauss))?$')
_PHASOR = re.compile(r'^(b|h|em|field(_t|_nt|_ut)?)[_.\- ]*(\*[_.\- ]*)?(real|re)([_.\- ]*\*)?'
                     r'([_.\- ]*(t|nt|ut))?$')
_IMAG = {'real': 'imag', 're': 'im'}
Triple = Tuple[str, str, str]


def axis_split(name: str) -> tuple[str, int] | None:
    """Return (vector key, axis index 0-2) from the last axis token of ``name``, or None."""
    tokens = re.split(r'([_.\- ]+)', normalize(name))
    for i in range(len(tokens) - 1, -1, -1):
        attached = _ATTACHED.match(tokens[i])
        if tokens[i] in AXES or attached:
            axis = attached.group(2) if attached else tokens[i]
            tokens[i] = f'{attached.group(1)}*' if attached else '*'
            return ''.join(tokens), AXES[axis]
    return None


def triples(names: list[str]) -> dict[str, Triple]:
    """Every complete (axis 0, 1, 2) column triple, keyed by vector key, in file order."""
    found: dict[str, dict[int, str]] = {}
    for name in names:
        split = axis_split(name)
        if split:
            found.setdefault(split[0], {}).setdefault(split[1], name)
    return {key: (axes[0], axes[1], axes[2]) for key, axes in found.items() if len(axes) == 3}


def magnetic_triple(names: list[str]) -> Triple:
    """The static B-field columns; a ``combined_`` (Earth + anomaly) vector is preferred.

    Raises:
        ValueError: if no complete B-field triple exists.
    """
    matches = [(not key.startswith('combined'), triple)
               for key, triple in triples(names).items() if _MAGNETIC.match(key)]
    if not matches:
        raise ValueError('no magnetic B-field columns (such as Bx/By/Bz, field_T_0..2 or '
                         'magnetic_x_gauss..z) found')
    return min(matches, key=lambda match: match[0])[1]


def phasor_triples(names: list[str]) -> tuple[Triple, Triple]:
    """The (real, imaginary) B-phasor column triples of an electromagnetic sensor.

    Raises:
        ValueError: if no real triple with a matching imaginary triple exists.
    """
    found = triples(names)
    for key, real in found.items():
        part = _PHASOR.match(key)
        if part:
            imag_key = key[:part.start(4)] + _IMAG[part.group(4)] + key[part.end(4):]
            if imag_key in found:
                return real, found[imag_key]
    raise ValueError('no electromagnetic phasor columns (such as Bx_re/Bx_im or '
                     'field_T_real_0..2/field_T_imag_0..2) found')


def unit_scale_nt(name: str) -> float:
    """Factor converting a B column to nT from the unit in its name (T, µT, nT, gauss).

    A name without a unit is assumed to be in nT already (factor 1).
    """
    lowered = name.lower()
    for token, scale in (('nt', 1.0), ('ut', 1e3), ('µt', 1e3), ('gauss', 1e5), ('t', 1e9)):
        if re.search(rf'(^|[_.\-\[( ]){token}($|[_.\-\]) ])', lowered):
            return scale
    return 1.0
