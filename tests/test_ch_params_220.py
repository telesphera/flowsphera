"""2.2.0: query parameters reach ClickHouse unchanged. A scalar value is read in ClickHouse's escaped format, so a
backslash (User-ID «corp\\anna»), a tab or a newline must be escaped; an array is a quoted literal and must not be
escaped twice. (Checked against a live ClickHouse 24.8 too.) Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
import common  # noqa: E402


class Params(unittest.TestCase):
    def sent(self, params):
        seen = {}

        class Resp:
            status = 200

            def read(self):
                return b''

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=None):
            from urllib.parse import parse_qs, urlparse
            seen.update({k: v[0] for k, v in parse_qs(urlparse(req.full_url).query, keep_blank_values=True).items()})
            return Resp()
        with mock.patch('urllib.request.urlopen', urlopen):
            try:
                common.ch('SELECT 1', params)
            except Exception:
                pass
        return seen

    def test_scalar_strings_are_escaped(self):
        q = self.sent({'u': 'corp\\anna', 't': 'a\tb', 'n': 'x\ny', 'p': 'plain', 'i': 5})
        self.assertEqual(q['param_u'], 'corp\\\\anna')
        self.assertEqual(q['param_t'], 'a\\tb')
        self.assertEqual(q['param_n'], 'x\\ny')
        self.assertEqual((q['param_p'], q['param_i']), ('plain', '5'))

    def test_arrays_are_one_literal(self):
        q = self.sent({'a': ['corp\\bob', "it's"], 'n': [1, 2]})
        self.assertEqual(q['param_a'], "['corp\\\\bob','it\\'s']")
        self.assertEqual(q['param_n'], '[1,2]')


if __name__ == '__main__':
    unittest.main()
