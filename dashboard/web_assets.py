"""Find the dashboard's browser files by name inside the grouped ``web/`` folder tree.

The pages ask for flat URLs (``/pose.js``, ``/style.css``) while the files live
in subfolders (``web/live/pose.js``, ``web/assets/style.css``). Every server
looks files up here, so moving a file between subfolders changes no URL.
Only plain file names are accepted, so a request cannot leave ``web/``.
"""
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / 'web'
MIME_TYPES = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png'}


class WebAssets:
    """Index of the files under one web root, keyed by their unique file name."""

    def __init__(self, root: Path = WEB):
        """Index every file below ``root``; raise ValueError when two share a name."""
        self.root = root
        self._paths = {}
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            if path.name in self._paths:
                raise ValueError(f'{path.name} appears twice under {root}')
            self._paths[path.name] = path

    def find(self, name: str) -> Path | None:
        """The path of the file called ``name``, or None for unknown names and sub-paths."""
        return self._paths.get(name)

    def path(self, name: str) -> Path:
        """The path of the file called ``name``; raise FileNotFoundError when there is none."""
        found = self.find(name)
        if found is None:
            raise FileNotFoundError(f'{name} is not a file under {self.root}')
        return found

    def read(self, name: str) -> bytes:
        """The bytes of the file called ``name``."""
        return self.path(name).read_bytes()

    @staticmethod
    def mime_type(name: str) -> str:
        """The Content-Type of ``name`` from its extension (octet-stream when unknown)."""
        return MIME_TYPES.get(Path(name).suffix, 'application/octet-stream')


ASSETS = WebAssets()
