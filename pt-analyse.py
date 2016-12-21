#!/usr/bin/env python3

import argparse
import os
from io import StringIO

import numpy as np
import pandas as pd

from pint import UnitRegistry
ureg = UnitRegistry()
Q_ = ureg.Quantity

known_datasets = {"process":
                  {"section": "Overview of Software Power Consumers",
                   "power": "PW Estimate",
                   "name": "Description"},
                  "device":
                  {"section": "Device Power Report",
                   "power": "PW Estimate",
                   "name": "Device Name"}}


def parse_single(path):
    fd = open(path)
    data = fd.read()
    fd.close()
    para = list(filter(len, data.split("_"*68 + "\n")))[1:]
    sections = {}
    for p in para:
        header, body = p.split("*  *  *\n\n")
        title = header[8:].strip()
        sections[title] = body.strip()
#        data = pd.read_csv(StringIO(body.strip()), delimiter=';')
    return sections


def get_section(data, name):
    body = data[name]
    data = pd.read_csv(StringIO(body.strip()), delimiter=';')
    return data


def list_files(path, prefix):
    import glob
    return list(map(os.path.abspath, glob.glob(os.path.join(path, prefix) + "*")))


def software_process_one(df):
    return df


def to_watt(x):
    if not isinstance(x, str):
        return x
    x = x.strip()
    if x == "nan" or x == "":
        return np.nan
    return Q_(x).to("watt").magnitude


def load_dataset(files, name):
    if name not in known_datasets:
        raise ValueError("Unknown dataset")
    ds = known_datasets[name]
    name_col = ds['name']
    combined = []
    for f in files:
        x = parse_single(f)
        df = get_section(x, ds["section"])
        ts = parse_date(f)
        df['time'] = ts
        df.drop(df.index[pd.isnull(df[name_col])], inplace=True)
        if 'power' in ds:
            c = ds['power']
            df['power'] = np.array(list(map(lambda x: to_watt(x), df[c])))
        combined.append(df)
    df = pd.concat(combined, ignore_index='True')
    df.rename(columns={name_col: "Name"}, inplace=True)
    return df


def parse_date(path):
    return pd.to_datetime(path[-15:], format='%Y%m%d-%H%M%S')


def parse_date_timestamp(path):
    return pd.to_datetime(path[-15:], format='%Y%m%d-%H%M%S').timestamp()


def find_periods(filelist, threashold=20):
    x = np.array(sorted(map(parse_date_timestamp, filelist)))
    d = np.diff(x)
    k = np.nonzero(d > threashold)[0]  # first dim
    s = np.hstack([[0], k+1])
    e = np.hstack([k, [len(d)]])  # len(d) == len(k) - 1
    r = [(x[i], x[j]) for i, j in zip(s, e)]
    return r


def ask_user_for_period(periods):
    from datetime import datetime
    from_ts = datetime.fromtimestamp
    make_ct = lambda x: from_ts(x).ctime()
    p = list(map(lambda x: (make_ct(x[0]), make_ct(x[1])), periods))
    choices = list(map(lambda x: str(x+1), range(len(p))))
    for i, c in enumerate(choices):
        print("%s. %s (until %s)" % (c, p[i][0], p[i][1]))
    print("*  Use all data")

    while True:
        try:
            got = input("choice: ")
        except KeyboardInterrupt:
            import sys
            sys.exit(1)
        if got in choices:
            return int(got) - 1
        elif got == '*':
            return None


def my_mean(x):
    x = np.array(list(filter(lambda x: not np.isnan(x), x)))
    if len(x) == 0:
        return np.nan
    return np.mean(x)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("prefix")
    args = parser.parse_args()

    fl = list_files(args.input, args.prefix)
    periods = find_periods(fl)
    if len(periods) > 1:
        c = ask_user_for_period(periods)
        if c is not None:
            s = periods[c]
            fl = list(filter(lambda x: s[0] <= parse_date_timestamp(x) <= s[1], fl))

    for kd in known_datasets.keys():
        ds = load_dataset(fl, kd)
        outname = "%s-%s.csv" % (args.prefix, kd)
        ds.to_csv(outname)


if __name__ == '__main__':
    main()
