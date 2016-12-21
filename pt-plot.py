#!/usr/bin/env python3
import argparse
import os

import matplotlib.cm as cmx
import matplotlib.colors as colors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


import numpy as np
import pandas as pd


def my_mean(x):
    x = np.array(list(filter(lambda x: not np.isnan(x), x)))
    if len(x) == 0:
        return np.nan
    return np.mean(x)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data")
    parser.add_argument('--style', nargs='*', type=str, default=['ggplot'])
    parser.add_argument('--save', action='store_true', default=False)
    args = parser.parse_args()

    style_check = [s not in plt.style.available for s in args.style]
    if any(style_check):
        print("[W] %s style not available." % args.style)
        print(" Known styles:\n\t%s" % "\n\t".join(plt.style.available))
    else:
        plt.style.use(args.style)

    ds = pd.read_csv(args.data, parse_dates=['time'])

    g = ds.groupby("Name")
    avg = g['power'].agg({"sum": np.nansum, "avg": my_mean})
    avg = avg.reset_index()
    avg.sort_values("sum", inplace=True, ascending=False)
    print(avg[:10])
    culprits = avg[:10]

    # plotting of the data
    cm = plt.get_cmap('jet')
    cNorm = colors.Normalize(vmin=0, vmax=10)
    scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=cm)

    fig, ax = plt.subplots()
    ds.sort_values('time', inplace=True)
    handles = []
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    for i, name in enumerate(culprits.Name):
        data = ds[ds.Name == name]
        c = scalarMap.to_rgba(len(culprits)-i)
        ah, = plt.plot(data['time'], data['power'], label=name, color=c)
        plt.plot_date(data['time'], data['power'], '.', color=c)
        handles += [ah]

    fig.autofmt_xdate()
    plt.title(args.data)
    plt.xlabel("time")
    plt.ylabel("power [W]")
    plt.legend(handles=handles)

    if args.save:
        name, ext = os.path.splitext(os.path.basename(args.data))
        outname = "%s.pdf" % name
        fig.set_size_inches(35, 15)
        fig.savefig(outname, papertype='a4', bbox_inches='tight', dpi=300)
    else:
        plt.show()


if __name__ == '__main__':
    main()
