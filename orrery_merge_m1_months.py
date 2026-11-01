#!/usr/bin/env python3
"""Merge multiple validated UTC M1 CSVs; never silently overwrite duplicate minutes."""
import argparse
import csv
import json
from pathlib import Path

FIELDS=("timestamp_utc","bid_open","bid_high","bid_low","bid_close")

def merge(paths, out):
    if len(paths)<2:
        raise ValueError("Provide at least two validated M1 CSV files")
    all_rows=[]
    for path in paths:
        with path.open(newline="",encoding="utf-8") as fp:
            reader=csv.DictReader(fp)
            if tuple(reader.fieldnames or ())!=FIELDS:
                raise ValueError(f"{path}: unexpected CSV columns")
            all_rows.extend(tuple(row[k] for k in FIELDS) for row in reader)
    all_rows.sort(key=lambda r:r[0])
    duplicates=0
    for index in range(1,len(all_rows)):
        if all_rows[index][0]==all_rows[index-1][0]:
            duplicates+=1
    if duplicates:
        raise ValueError(f"{duplicates} overlapping timestamps: merge aborted, no overwrites")
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="",encoding="utf-8") as fp:
        writer=csv.writer(fp)
        writer.writerow(FIELDS)
        writer.writerows(all_rows)
    return {"merged_m1_rows":len(all_rows),"first_utc":all_rows[0][0] if all_rows else None,
            "last_utc":all_rows[-1][0] if all_rows else None,
            "source_files":[str(x) for x in paths],"gap_filling":False,
            "duplicate_overwrites":0,"profits_verified":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("inputs",nargs="+",type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(merge(a.inputs,a.out),indent=2))
