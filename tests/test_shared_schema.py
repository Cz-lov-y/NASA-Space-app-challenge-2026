"""Ensure the shared, explicitly synthetic handoff example matches A's API."""
import json
import unittest
from examples.shared_schema import build_example


class SharedSchemaTests(unittest.TestCase):
    def test_example_has_primary_indicators_scope_and_unverified_report(self):
        e = build_example()
        self.assertEqual(e['example_status'], 'SYNTHETIC_EXAMPLE_NOT_OBSERVATIONS')
        self.assertEqual({r['variable'] for r in e['B_to_A']['rows_excerpt']}, {'ndvi', 'soil_water_0_10cm'})
        self.assertTrue(all('SYNTHETIC' in r['source'] for r in e['B_to_A']['rows_excerpt']))
        self.assertEqual(e['A_to_C_D']['observation_period']['years'], list(range(2003, 2025)))
        self.assertEqual(e['A_to_C_D']['scope'], 'global_exploratory')
        self.assertEqual(e['A_to_C_D']['divergence_status'], 'not_assessed')
        self.assertIsNone(e['A_to_C_D']['divergence_detected'])
        self.assertEqual(e['C_to_D_shape_only']['verification_status'], 'not_started')
        self.assertEqual(e['C_to_D_shape_only']['citations'], [])
        json.dumps(e, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
