#!/usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.cm as cmx
import pandas as pd
import argparse


def my_mean(x):
    x = np.array(list(filter(lambda x: not np.isnan(x), x)))
    if len(x) == 0:
        return np.nan
    return np.mean(x)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data")
    args = parser.parse_args()

    ds = pd.read_csv(args.data, parse_dates=['time'])

    g = ds.groupby("Name")
    avg = g['power'].agg({"sum": np.nansum, "avg": my_mean})
    avg = avg.reset_index()
    avg.sort_values("sum", inplace=True, ascending=False)
    print(avg[:10])
    culprits = avg[:10]

    # plotting of the data
    jet = cm = plt.get_cmap('jet')
    cNorm  = colors.Normalize(vmin=0, vmax=10)
    scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=jet)

    fig, ax = plt.subplots()
    ds.sort_values('time', inplace=True)
    handles = []
    for i, name in enumerate(avg[:10].Name):
        data = ds[ds.Name == name]
        c = scalarMap.to_rgba(10-i)
        ah, = plt.plot(data['time'], data['power'], label=name, color=c)
        plt.plot_date(data['time'], data['power'], color=c)
        handles += [ah]

    fig.autofmt_xdate()
    plt.title(args.data)
    plt.xlabel("time")
    plt.ylabel("power [W]")
    plt.legend(handles=handles)
    plt.show()

if __name__ == '__main__':
    main()
