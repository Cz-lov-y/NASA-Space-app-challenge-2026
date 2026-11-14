# Member B real-data interface handoff

The committed NASA-derived series are preliminary and are now available through `src.nasa_data.get_timeseries`. `whole_earth` supports `ndvi`, `soil_water_0_10cm`, and `soil_water_0_100cm`; `central_us_sample` supports only `soil_water_0_10cm`. `demo-region` remains explicitly synthetic. The full-Earth series preserve 287 monthly rows through November 2026, with unavailable observations represented as NaN and coverage flags retained. The required 2003–2024 period has 264 nonmissing months per variable.

```python
from copy import deepcopy
import pandas as pd
from src.nasa_data import get_timeseries
from src.statistics import analyze_region

frames = [get_timeseries('whole_earth', name)
          for name in ('ndvi', 'soil_water_0_100cm')]
provenance = {f.variable.iloc[0]: deepcopy(f.attrs['metadata']) for f in frames}
data = pd.concat(frames, ignore_index=True)
data = data[data.date.between('2003-01-01', '2024-12-01')]
result = analyze_region(data, soil_moisture_variable='soil_water_0_100cm')
```

Preserve `provenance` separately: DataFrame attributes may be discarded by concatenation or serialization. The durable catalog is `data/processed/series_metadata.json`; source-specific methods and known limits are documented in `data/processed/global_combined/metadata.md` and the sample's metadata. Units are NDVI `1` and soil water storage `kg m-2`. Never rename storage as volumetric moisture. The generic `validate_timeseries` remains strict by default; `allow_missing=True` is used by the reader to preserve real missing values, while malformed numbers and infinity remain errors.

All nonmissing global results retain `coverage_review_required`. The statistics engine does not incorporate these spatial QA flags into its numerical classification. It can produce a supported statistical signal without validating MODIS/GLDAS geographic overlap, source provenance or scientific assumptions. Global coverage denominators include oceans; MODIS and GLDAS footprints differ, and equal region IDs do not establish overlap. Independent MODIS aggregation validation and team review remain outstanding. The local MODIS inputs are derived Earth Engine exports; cloud asset references are not local archives of original rasters.

The dashboard now supports the real region IDs and depth-specific soil variables, passes the explicit soil name to statistics, and displays the whole-Earth footprint warning and provenance. The default remains the synthetic demo. Member D should review the integration and presentation. Do not represent a whole-Earth mean as a local environmental or policy finding. For tests use `python -m pytest -q tests/test_data.py tests/test_global_handoff.py tests/test_statistics.py`; the team CI specifies Python 3.12.
