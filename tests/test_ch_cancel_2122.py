"""(2.12.2) A ClickHouse query cancelled after its answer began (a page reloaded: KILL QUERY) may come back as HTTP 200
with the error inside the JSON («data»: [], «exception»: «Code: 394 …») or cut short. common.ch raises CHError (the API
answers 409 «cancelled»), never returns «no rows» (a traceback in /api/summary, Lab smoke #184)."""
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import common  # noqa: E402

CANCELLED = '{"meta":[{"name":"c","type":"UInt64"}],"data":[],"rows":0,"exception":"Code: 394. DB::Exception: Query was cancelled. (QUERY_WAS_CANCELLED)"}'


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Cancelled(unittest.TestCase):
    def ask(self, out):
        with mock.patch('urllib.request.urlopen', return_value=Answer(out.encode())):
            return common.ch('SELECT 1 AS c', fmt='JSON')

    def test_error_inside_a_200_answer(self):
        with self.assertRaises(common.CHError) as e:
            self.ask(CANCELLED)
        self.assertIn('Code: 394', str(e.exception))

    def test_cut_short_answer(self):
        with self.assertRaises(common.CHError):
            self.ask('{"meta":[{"name":"c"}],"data":[{"c":"1"}')

    def test_normal_answer(self):
        self.assertEqual(self.ask('{"meta":[],"data":[{"c":"1"}],"rows":1}'), [{'c': '1'}])


if __name__ == '__main__':
    unittest.main()
