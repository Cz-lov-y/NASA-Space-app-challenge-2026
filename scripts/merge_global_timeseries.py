#!/usr/bin/env python3
"""Audit Earth Engine exports and join them to the global GLDAS series."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/modis_earth_engine'
OUT=ROOT/'data/processed/global_combined'
OUT.mkdir(parents=True,exist_ok=True)
files=sorted(RAW.glob('mod13a3_whole_earth_20[0-9][0-9].csv'))
repair=RAW/'mod13a3_missing_months_repair.csv'
if repair.exists(): files.append(repair)
if len(files)<24: raise ValueError('Expected 24 yearly exports')
frames=[]
for p in files:
 d=pd.read_csv(p, dtype={'unit':str})
 if p!=repair and not d.date.str.startswith(p.stem[-4:]).all(): raise ValueError(f'Wrong year: {p}')
 frames.append(d)
modis=pd.concat(frames,ignore_index=True)
if modis.date.duplicated().any(): raise ValueError('Duplicate MODIS month')
if not ((modis.region_id=='whole_earth') & (modis.variable=='ndvi') & (modis.source=='MOD13A3.061') & (modis.unit=='1')).all(): raise ValueError('Unexpected MODIS provenance')
valid=modis.value.notna()
if not (modis.loc[valid,'value'].between(-.2,1).all() and modis.loc[valid,'valid_area_fraction'].between(0,1).all() and (modis.loc[valid,'source_image_count']==1).all()): raise ValueError('Unexpected MODIS value, coverage or image count')
if not np.allclose(modis.loc[valid,'valid_area_m2']/modis.loc[valid,'region_area_m2'],modis.loc[valid,'valid_area_fraction'],rtol=1e-9): raise ValueError('Area mismatch')
if not (modis.loc[valid,'qa_rule']=='raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0').all(): raise ValueError('Unexpected QA rule')
index=pd.DataFrame({'date':pd.date_range('2003-01-01','2026-11-01',freq='MS').strftime('%Y-%m-%d')})
if not modis.date.isin(index.date).all(): raise ValueError('Unexpected MODIS month')
ndvi=index.merge(modis,on='date',how='left',validate='one_to_one')
for k,v in {'region_id':'whole_earth','variable':'ndvi','unit':'1','source':'MOD13A3.061','quality_flag':'missing_export'}.items(): ndvi[k]=ndvi[k].fillna(v)
cols=['date','region_id','variable','value','unit','source','valid_area_fraction','quality_flag']
soil=pd.read_csv(ROOT/'data/processed/global_gldas/monthly_timeseries.csv')
combined=pd.concat([ndvi[cols],soil[cols]],ignore_index=True).sort_values(['date','variable'])
combined.to_csv(OUT/'monthly_timeseries.csv',index=False)
reports=[]
for period,subset in [('required_2003_2024',combined[combined.date<='2024-12-01']),('extended_2003_2026_11',combined)]:
 for variable,g in subset.groupby('variable'):
  reports.append(dict(period=period,variable=variable,expected_months=len(g),valid_months=int(g.value.notna().sum()),missing_months=int(g.value.isna().sum()),missing_dates=';'.join(g.loc[g.value.isna(),'date']),minimum_value=g.value.min(),maximum_value=g.value.max(),min_coverage=g.valid_area_fraction.min(),mean_coverage=g.valid_area_fraction.mean(),max_coverage=g.valid_area_fraction.max(),flags=json.dumps(g.quality_flag.value_counts().to_dict(),sort_keys=True)))
pd.DataFrame(reports).to_csv(OUT/'quality_report.csv',index=False)
manifest=[{'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
(OUT/'modis_source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for variable,name in [('ndvi','ndvi_timeseries.png'),('soil_water_0_100cm','soil_water_timeseries.png')]:
 d=combined[combined.variable==variable]; fig,ax=plt.subplots(figsize=(12,4));ax.plot(pd.to_datetime(d.date),d.value);ax.set(title=variable,ylabel='NDVI' if variable=='ndvi' else 'kg m-2');fig.tight_layout();fig.savefig(OUT/name,dpi=150);plt.close(fig)
print(pd.DataFrame(reports)[['period','variable','expected_months','valid_months','missing_months','missing_dates']].to_string(index=False))
