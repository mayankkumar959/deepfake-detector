"""Safety checks for bounded partial downloads from public research archives."""
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('video_downloads', Path(__file__).resolve().parents[1] / 'prepare_video_manipulations.py')
downloads = importlib.util.module_from_spec(spec)
spec.loader.exec_module(downloads)


def response(status, content_range=None, body=b''):
    item = MagicMock()
    item.status_code = status
    item.headers = {'Content-Range': content_range} if content_range else {}
    item.raw = io.BytesIO(body)
    item.__enter__.return_value = item
    return item


class ArchiveRangeTests(unittest.TestCase):
    def test_full_archive_response_is_refused(self):
        with patch.object(downloads.requests, 'get', return_value=response(200)):
            with self.assertRaises(ValueError):
                downloads.RemoteZip('https://example.invalid/archive.zip')

    def test_range_read_and_cached_seek(self):
        head = response(206, 'bytes 0-0/10', b'a')
        part = response(206, 'bytes 0-9/10', b'abcdefghij')
        with patch.object(downloads.requests, 'get', side_effect=[head, part]) as get:
            remote = downloads.RemoteZip('https://example.invalid/archive.zip')
            self.assertEqual(remote.read(3), b'abc')
            remote.seek(5)
            self.assertEqual(remote.read(2), b'fg')
            remote.seek(-2, 2)
            self.assertEqual(remote.read(2), b'ij')
            self.assertEqual(remote.read(1), b'')
            self.assertEqual(get.call_count, 2)

    def test_ignored_range_is_refused(self):
        with patch.object(downloads.requests, 'get', side_effect=[response(206, 'bytes 0-0/10'), response(200)]):
            remote = downloads.RemoteZip('https://example.invalid/archive.zip')
            with self.assertRaises(ValueError):
                remote.read(2)

    def test_invalid_offset_is_refused(self):
        with patch.object(downloads.requests, 'get', return_value=response(206, 'bytes 0-0/10')):
            remote = downloads.RemoteZip('https://example.invalid/archive.zip')
            with self.assertRaises(ValueError):
                remote.seek(-1)
            with self.assertRaises(ValueError):
                remote.seek(11)


if __name__ == '__main__':
    unittest.main()
