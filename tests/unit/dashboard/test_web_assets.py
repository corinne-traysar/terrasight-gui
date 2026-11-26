"""Tests of dashboard/web_assets.py: finding browser files by name in the web/ tree."""
from pathlib import Path
import tempfile
import unittest

from dashboard.web_assets import ASSETS, WEB, WebAssets


class WebAssetsTests(unittest.TestCase):
    """A temporary web tree with files in nested subfolders."""

    def setUp(self):
        """Create web/pages/index.html and web/live/js/app.js."""
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        (self.root / 'pages').mkdir()
        (self.root / 'live' / 'js').mkdir(parents=True)
        (self.root / 'pages' / 'index.html').write_bytes(b'<html>')
        (self.root / 'live' / 'js' / 'app.js').write_bytes(b'app()')
        self.assets = WebAssets(self.root)

    def tearDown(self):
        """Remove the temporary tree."""
        self.folder.cleanup()

    def test_find_returns_nested_files_by_name(self):
        self.assertEqual(self.assets.find('app.js'), self.root / 'live' / 'js' / 'app.js')
        self.assertEqual(self.assets.read('index.html'), b'<html>')

    def test_sub_paths_and_unknown_names_are_not_found(self):
        for name in ('pages/index.html', '../index.html', 'missing.js', ''):
            self.assertIsNone(self.assets.find(name), name)

    def test_path_of_an_unknown_name_raises(self):
        with self.assertRaisesRegex(FileNotFoundError, 'missing.js'):
            self.assets.path('missing.js')

    def test_duplicate_names_are_refused(self):
        (self.root / 'live' / 'index.html').write_bytes(b'copy')
        with self.assertRaisesRegex(ValueError, 'index.html appears twice'):
            WebAssets(self.root)

    def test_mime_type_follows_the_extension(self):
        self.assertEqual(WebAssets.mime_type('a.js'), 'text/javascript')
        self.assertEqual(WebAssets.mime_type('a.css'), 'text/css')
        self.assertEqual(WebAssets.mime_type('a.png'), 'image/png')
        self.assertEqual(WebAssets.mime_type('a.bin'), 'application/octet-stream')


class RepositoryWebTreeTests(unittest.TestCase):
    """The real web/ folder: every page and script the servers name can be found."""

    def test_root_is_the_repository_web_folder(self):
        self.assertEqual(WEB.name, 'web')
        self.assertTrue((WEB.parent / 'dashboard' / 'web_assets.py').is_file())

    def test_every_folder_holds_at_most_ten_files(self):
        for folder in [WEB, *(p for p in WEB.rglob('*') if p.is_dir())]:
            files = [p for p in folder.iterdir() if p.is_file()]
            self.assertLessEqual(len(files), 10, folder)

    def test_pages_and_shared_files_are_indexed(self):
        for name in ('index.html', 'bench.html', 'style.css', 'pose.js', 'scan-plot.js', 'vn100-reference.png'):
            self.assertIsNotNone(ASSETS.find(name), name)


if __name__ == '__main__':
    unittest.main()
