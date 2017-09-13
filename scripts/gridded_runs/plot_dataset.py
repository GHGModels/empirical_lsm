#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: plot_dataset.py
Author: naught101
Email: naught101@email.com
Github: https://github.com/naught101/empirical_lsm
Description: Plots annual and monthly means and standard deviations of gridded model outputs.

Usage:
    plot_dataset.py year <name> <variable> <year>
    plot_dataset.py (-h | --help | --version)

Options:
    -h, --help    Show this screen and exit.
"""

from docopt import docopt

import os
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

from mpl_toolkits import basemap
from mpl_toolkits.axes_grid1 import ImageGrid
from matplotlib.colors import LinearSegmentedColormap

from empirical_lsm.gridded_datasets import get_MODIS_data  # , get_GLEAM3a_data, get_MPI_data

from pals_utils.logging import setup_logger
logger = setup_logger(__name__, 'logs/plot_dataset.log')


def get_range(x):
    return np.quantile(x, [0, 100])


def colormap(x0):
    """custom colourmap for map plots"""

    if x0 > 0:
        x2 = (1 + 2 * x0) / 3.0
        x3 = (2 + x0) / 3.0

        # blue, white, red, yellow, purple
        cdict1 = {'red': ((0.0, 0.0, 0.0),
                          (x0, 0.9, 0.9),
                          (x2, 1.0, 1.0),
                          (x3, 1.0, 1.0),
                          (1.0, 1.0, 1.0)),
                  'green': ((0.0, 0.0, 0.0),
                            (x0, 0.9, 0.9),
                            (x2, 0.0, 0.0),
                            (x3, 1.0, 1.0),
                            (1.0, 0.0, 0.0)),
                  'blue': ((0.0, 1.0, 1.0),
                           (x0, 0.9, 0.9),
                           (x2, 0.0, 0.0),
                           (x3, 0.0, 0.0),
                           (1.0, 1.0, 1.0))
                  }
        N = 20
    else:
        x2 = 1 / 3.0
        x3 = 2 / 3.0
        cdict1 = {'red': ((x0, 0.9, 0.9),
                          (x2, 1.0, 1.0),
                          (x3, 1.0, 1.0),
                          (1.0, 1.0, 1.0)),
                  'green': ((x0, 0.9, 0.9),
                            (x2, 0.0, 0.0),
                            (x3, 1.0, 1.0),
                            (1.0, 0.0, 0.0)),
                  'blue': ((x0, 0.9, 0.9),
                           (x2, 0.0, 0.0),
                           (x3, 0.0, 0.0),
                           (1.0, 1.0, 1.0))
                  }
        N = 15

    return LinearSegmentedColormap('BlueRed1', cdict1, N=N)


def plot_array(da, ax=None, shift=True, cmap=None, vmin=None, vmax=None):
    """plots an array of lat by lon on a coastline map"""

    m = basemap.Basemap()
    # m.drawcoastlines()

    if np.any(np.isnan(da)):
        masked_data = np.ma.masked_where(np.isnan(da), da).T
    else:
        lons = da.lon.values
        lons[lons > 180] -= 360
        lons, lats = np.meshgrid(lons, da.lat)
        masked_data = basemap.maskoceans(lonsin=lons, latsin=lats, datain=da.T)

    m.pcolormesh(da.lon, y=da.lat, data=masked_data, latlon=True, vmin=vmin, vmax=vmax, cmap=cmap)

    return m


def get_benchmark_filename(name, variable, year):
    template = "data/gridded_benchmarks/{n}/{n}_{v}_{y}.nc"
    filename = template.format(n=name, v=variable, y=year)

    return filename


def month_name(n):
    """get month name from number
    """
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
              'August', 'September', 'October', 'November', 'December']

    return months[n]


def get_means(da):
    """get monthly and annual means"""
    monthly_mean = da.groupby('time.month').mean(dim='time').copy()
    annual_mean = monthly_mean.mean(dim='month')

    return monthly_mean, annual_mean


def get_stds(da):
    """get standard deviations, annual and monthly
    """
    monthly_std = da.groupby('time.month').std(dim='time').copy()
    annual_std = da.std(dim='time').copy()
    return monthly_std, annual_std


def p_monthly_mean(data, name, variable, year):
    logger.info("Plotting monthly mean grid")
    cmap = colormap(0.25)
    vmin, vmax = [-50, 150]  # estimate with some leeway
    fig = plt.figure(0, (14, 8))
    grid = ImageGrid(fig, 111, nrows_ncols=(3, 4), axes_pad=0.3,
                     cbar_mode='single', cbar_location="bottom",)
    for i in range(12):
        plt.sca(grid[i])
        plot_array(data.sel(month=i + 1), vmin=vmin, vmax=vmax, cmap=cmap)
        plt.title(month_name(i))
    plt.suptitle("{n} - {y} {v} monthly means".format(n=name, y=year, v=variable))
    plt.colorbar(cax=grid[0].cax, orientation='horizontal')
    plt.tight_layout()

    os.makedirs("plots/monthly_means/{y}".format(y=year), exist_ok=True)
    plt.savefig("plots/monthly_means/{y}/{n}_{y}_{v}_monthly_means.png".format(n=name, y=year, v=variable))
    plt.close()


def p_monthly_stdev(data, name, variable, year):
    logger.info("Plotting monthly std dev grid")
    cmap = colormap(0)
    vmin, vmax = [0, 150]  # estimate with some leeway
    fig = plt.figure(0, (14, 8))
    grid = ImageGrid(fig, 111, nrows_ncols=(3, 4), axes_pad=0.3,
                     cbar_mode='single', cbar_location="bottom",)
    for i in range(12):
        plt.sca(grid[i])
        plot_array(data.sel(month=i + 1), vmin=vmin, vmax=vmax, cmap=cmap)
        plt.title(month_name(i))
    plt.suptitle("{n} - {y} {v}_monthly std devs".format(n=name, y=year, v=variable))
    plt.colorbar(cax=grid[0].cax, orientation='horizontal')
    plt.tight_layout()

    os.makedirs("plots/monthly_stds/{y}".format(y=year), exist_ok=True)
    plt.savefig("plots/monthly_stds/{y}/{n}_{y}_{v}_monthly_stdev.png".format(n=name, y=year, v=variable))
    plt.close()


def p_annual_mean(data, name, variable, year):
    logger.info("Plotting annual Mean")
    # Standardised color profiles for monthly means
    cmap = colormap(0.2)
    vmin, vmax = [-25, 100]  # estimate with some leeway
    plt.figure(0, (10, 5))
    plot_array(data, vmin=vmin, vmax=vmax, cmap=cmap)
    plt.title("{n} - {y} {v}_annual mean".format(n=name, y=year, v=variable))
    plt.tight_layout()
    plt.colorbar(fraction=0.1, shrink=0.8)

    os.makedirs("plots/annual_mean/{y}".format(y=year), exist_ok=True)
    plt.savefig("plots/annual_mean/{y}/{n}_{y}_{v}_annual_mean.png".format(n=name, y=year, v=variable))
    plt.close()


def p_annual_stdev(data, name, variable, year):
    logger.info("Plotting annual Std dev")
    cmap = colormap(0)
    vmin, vmax = [0, 150]  # estimate with some leeway
    plt.figure(0, (10, 5))
    plot_array(data, vmin=vmin, vmax=vmax, cmap=cmap)
    plt.title("{n} - {y} {v}_annual std dev".format(n=name, y=year, v=variable))
    plt.tight_layout()
    plt.colorbar(fraction=0.1, shrink=0.8)

    os.makedirs("plots/annual_std/{y}".format(y=year), exist_ok=True)
    plt.savefig("plots/annual_std/{y}/{n}_{y}_{v}_annual_stdev.png".format(n=name, y=year, v=variable))
    plt.close()


def plot_benchmark_year(name, variable, year):
    filename = get_benchmark_filename(name, variable, year)

    # load file
    with xr.open_dataset(filename) as ds:
        da = ds[variable].copy()
        monthly_mean, annual_mean = get_means(da)
        monthly_std, annual_std = get_stds(da)

    p_monthly_mean(monthly_mean, name, variable, year)
    p_monthly_stdev(monthly_std, name, variable, year)
    p_annual_mean(annual_mean, name, variable, year)
    p_annual_stdev(annual_std, name, variable, year)


def plot_year(name, variable, year):
    """Plots annual and monthly means and std devs.
    """

    if any([name.startswith(s) for s in ["1lin", "3km", "5km"]]):
        # We're a bencmark
        plot_benchmark_year(name, variable, year)

    elif any([name.startswith(s) for s in ["GLEAM", "MODIS", "MPI"]]):
        if name.startswith("MODIS"):
            monthly_mean = get_MODIS_data([variable], year).rename({'months': 'month'})['Qle']
            p_monthly_mean(monthly_mean, name, variable, year)
            annual_mean = monthly_mean.mean(dim='month')
            p_annual_mean(annual_mean, name, variable, year)
        # elif name.startswith("GLEAM"):
        #     # TODO: convert days to months
        #     data = get_GLEAM3a_data([variable], year)
        # elif name.startswith("MPI"):
        #     # TODO: convert time to months
        #     data = get_MPI_data([variable], year)
    else:
        raise Exception("What the hell is %s?" % name)


def plot_all_years(name, variable, years):
    """TODO: Docstring for plot_all_years.

    :name: TODO
    :returns: TODO

    """
    for y in range(*years):
        # get annual data
        # get means
        # close dataset
        pass


def main(args):

    if args['year']:
        plot_year(args['<name>'], args['<variable>'], args['<year>'])
    elif args['all-years']:
        plot_all_years(args['<name>'], args['<variable>'], years=[2000, 2007])

    return


if __name__ == '__main__':
    args = docopt(__doc__)

    main(args)
