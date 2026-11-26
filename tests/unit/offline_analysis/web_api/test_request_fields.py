"""Tests of web_api/request_fields.py: typed access to the JSON request fields."""
import math
import unittest

from calibration_model import MISSING
from offline_analysis.web_api.request_fields import RequestFields, clean, finite_number

SCAN = 't,Bx,By\n0,1,10\n1,2,20\n2,3,30\n'


class FieldTests(unittest.TestCase):
    """text, number and get, with the field name in every error."""

    def test_text_and_get(self):
        fields = RequestFields({'name': 'scan.csv', 'method': 'imu'})
        self.assertEqual(fields.text('name'), 'scan.csv')
        self.assertEqual((fields.get('method'), fields.get('missing', 'auto')), ('imu', 'auto'))
        with self.assertRaisesRegex(ValueError, 'text must be text'):
            fields.text('text')

    def test_numbers_must_be_finite_and_not_bool(self):
        fields = RequestFields({'start': 1, 'end': 2.5})
        self.assertEqual((fields.number('start'), fields.number('end')), (1.0, 2.5))
        self.assertEqual(fields.number('reference_nt', 45000), 45000.0)
        for bad in (True, 'a', None, math.nan, math.inf):
            with self.subTest(value=bad), self.assertRaisesRegex(ValueError, 'start must be a finite number'):
                finite_number(bad, 'start')


@unittest.skipIf(MISSING, MISSING or '')
class ScanFieldTests(unittest.TestCase):
    """scan, magnetic and cropped read the file text in the request with onyx."""

    def test_scan_is_parsed_with_its_name(self):
        name, scan = RequestFields({'name': 'scan.csv', 'text': SCAN}).scan()
        self.assertEqual((name, scan.rows, scan.channels), ('scan.csv', 3, ['Bx', 'By']))

    def test_magnetic_needs_a_field_triple(self):
        text = 't,Bx,By,Bz\n0,1,2,3\n'
        self.assertEqual(RequestFields({'name': 's.csv', 'text': text}).magnetic().sensor_columns, ('Bx', 'By', 'Bz'))
        with self.assertRaisesRegex(ValueError, 'no magnetic field'):
            RequestFields({'name': 's.csv', 'text': SCAN}).magnetic()

    def test_cropped_keeps_the_window_and_channels(self):
        # [0.5, 2] keeps t = 1 and 2.
        cropped = RequestFields({'name': 's.csv', 'text': SCAN, 'start': .5, 'end': 2, 'channels': ['By']}).cropped()
        self.assertEqual({k: list(v) for k, v in cropped.columns.items()}, {'t': [1.0, 2.0], 'By': [20.0, 30.0]})

    def test_channels_must_be_a_list_of_names(self):
        for channels in ('Bx', [1], None):
            fields = RequestFields({'name': 's.csv', 'text': SCAN, 'start': 0, 'end': 1, 'channels': channels})
            with self.subTest(channels=channels), self.assertRaisesRegex(ValueError, 'channels must be a list'):
                fields.cropped()


class CleanTests(unittest.TestCase):
    """clean: NaN and infinities become None for JSON."""

    def test_non_finite_values_become_none(self):
        self.assertEqual(clean([1.0, math.nan, math.inf, -2.0]), [1.0, None, None, -2.0])


if __name__ == '__main__':
    unittest.main()
