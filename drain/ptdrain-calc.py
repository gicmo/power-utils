#!/usr/bin/env python3
import argparse
import sys

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default='/var/cache/pt/drain.csv')
    parser.add_argument('--style', nargs='*', type=str, default=['ggplot'])
    parser.add_argument('--save', action='store_true', default=False)
    args = parser.parse_args()

    ds = pd.read_csv(args.data)
    print(ds)

    data = []
    it = ds.itertuples()
    for row in it:
        action = row.action

        if action == 'check':
            continue
        if action != 'pre':
            print('ummatched or unkown action: %s' % action, file=sys.stderr)
            continue

        pre_ac, pre_ts, pre_energy = row.ac, row.timestamp, row.energy_total
        row = next(it)
        post_ac, post_ts, post_energy = row.ac, row.timestamp, row.energy_total

        if pre_ac or post_ac:
            continue

        duration = post_ts - pre_ts
        consumed = pre_energy - post_energy
        data.append((duration, consumed))

    data = np.array(data, dtype=float)
    data[:, 0] = data[:, 0] / 3600.0 # duration in h
    print(data, file=sys.stderr)
    watt = (data[:, 1]) / data[:, 0]
    avg = watt.mean(axis=0)
    print("Average consumed power during suspend: %.2f mW" % (avg / 1000))


if __name__ == '__main__':
    main()
