"""Readers that turn the text of a scan file into a Scan: delimited text or JSON.

Text: the first non-blank line is the header (a leading ``#`` is dropped); the
delimiter is a comma, tab or semicolon when the header has one, else
whitespace. JSON: a list of records, or an object holding one (``samples``
first); nested objects and lists are flattened to ``key_sub`` / ``key_0``
names. Both then share the numeric conversion and the sample-axis choice.
"""
from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from offline_analysis.scans.channels import find_axis
from offline_analysis.scans.column_parser import ColumnParser
from offline_analysis.scans.scan import Scan, with_row_axis

DELIMITERS = (',', '\t', ';')


class ScanReader(ABC):
    """Template: split the file into string columns, convert them, pick the sample axis."""

    def __init__(self, parser: ColumnParser | None = None):
        """Convert columns with ``parser`` (a default ColumnParser when None)."""
        self.parser = parser or ColumnParser()

    @staticmethod
    def for_name(name: str) -> ScanReader:
        """The reader for the file called ``name``: JSON for ``.json`` (any case), else text."""
        return JsonScanReader() if Path(name).suffix.lower() == '.json' else TextScanReader()

    def read(self, text: str) -> Scan:
        """The scan in ``text`` (a leading byte-order mark is ignored).

        Raises:
            ValueError: if the file has no rows or no numeric column, or is invalid.
        """
        columns = self.parser.numeric_columns(self.table(text.lstrip('﻿')))
        axis = find_axis(columns)
        return Scan(axis, columns) if axis else with_row_axis(columns)

    @abstractmethod
    def table(self, text: str) -> dict[str, list[str]]:
        """The file's header-named string columns."""


class TextScanReader(ScanReader):
    """Comma, tab, semicolon or whitespace separated text with one header line."""

    def table(self, text: str) -> dict[str, list[str]]:
        """Split delimited text into header-named string columns (short rows padded with '')."""
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            raise ValueError('the scan needs a header line and at least one data row')
        header = lines[0].lstrip('#').strip()
        delimiter = next((d for d in DELIMITERS if d in header), None)
        rows = list(csv.reader(lines, delimiter=delimiter)) if delimiter else [l.split() for l in lines]
        names = [name.strip() for name in (rows[0] if delimiter else header.split())]
        return {name: [row[i].strip() if i < len(row) else '' for row in rows[1:]]
                for i, name in enumerate(names)}


class JsonScanReader(ScanReader):
    """A JSON list of (possibly nested) records, or an object holding such a list."""

    def table(self, text: str) -> dict[str, list[str]]:
        """Flatten the records into string columns named after the first record."""
        flat = [self.flatten(record) for record in self.records(json.loads(text))]
        return {name: [str(row.get(name, '')) for row in flat] for name in flat[0]}

    @staticmethod
    def records(data: Any) -> list[dict[str, Any]]:
        """The record list of a JSON document, preferring a ``samples`` key.

        Raises:
            ValueError: if no non-empty list of objects is found.
        """
        if isinstance(data, dict):
            lists = [data.get('samples')] + list(data.values())
            data = next((v for v in lists if isinstance(v, list) and v and isinstance(v[0], dict)), None)
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise ValueError('the JSON scan must be a list of records or hold one')
        return data

    def flatten(self, value: Any, prefix: str = '') -> dict[str, Any]:
        """Flatten nested dicts/lists into ``{'a_b_0': leaf}``; booleans are dropped."""
        if isinstance(value, dict):
            items = value.items()
        elif isinstance(value, list):
            items = ((str(i), v) for i, v in enumerate(value))
        else:
            return {} if isinstance(value, bool) else {prefix: value}
        out: dict[str, Any] = {}
        for key, item in items:
            out.update(self.flatten(item, f'{prefix}_{key}' if prefix else str(key)))
        return out
