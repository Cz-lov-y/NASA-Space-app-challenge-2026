"""Contract and integration checks for synthetic mock data."""
import unittest

import pandas as pd

from examples.mock_data import mock_timeseries
from src.statistics import analyze_region


class MockContractTests(unittest.TestCase):
    def test_schema_metadata_and_statistics_integration(self):
        frames = [mock_timeseries("synthetic_region", name) for name in ("ndvi", "soil_moisture")]
        for frame in frames:
            self.assertEqual(set(frame.columns), {"date", "value", "unit", "variable", "source", "region_id"})
            self.assertEqual(len(frame), 192)
            self.assertTrue(frame.date.is_monotonic_increasing)
            self.assertFalse(frame.date.dt.to_period("M").duplicated().any())
            self.assertTrue(frame.source.str.contains("SYNTHETIC").all())
            self.assertEqual(set(frame.attrs["metadata"]), {"spatial_coverage", "time_range", "temporal_resolution", "dataset_version", "quality_control"})
            self.assertEqual(frame.attrs["metadata"]["quality_control"]["missing_count"], 0)
        provenance = {f.variable.iloc[0]: f.attrs["metadata"] for f in frames}
        result = analyze_region(pd.concat(frames, ignore_index=True))
        self.assertEqual(set(provenance), {"NDVI", "soil_moisture"})
        self.assertTrue(result["data_quality"]["synthetic_demo"])
        self.assertEqual(result["divergence"]["category"], "Supported Signal")

    def test_unsupported_requests_raise(self):
        for region, variable in (("Toronto", "NDVI"), ("synthetic_region", "precipitation")):
            with self.subTest(region=region, variable=variable), self.assertRaises(ValueError):
                mock_timeseries(region, variable)


if __name__ == "__main__":
    unittest.main()
