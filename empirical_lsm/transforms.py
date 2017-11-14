#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: transforms.py
Author: naughton101
Email: naught101@email.com
Github: https://github.com/naught101/empirical_lsm
Description: Transformations for empirical_lsm
"""

import re
import pandas as pd
import numpy as np
import xarray as xr

from collections import OrderedDict
from sklearn.utils.validation import check_is_fitted
from sklearn.base import BaseEstimator, TransformerMixin

import logging
logger = logging.getLogger(__name__)


class Mean(BaseEstimator):
    """Base class for Linear Models"""

    def fit(self, X, y):
        """Fit model."""
        self.mean = y.mean(axis=0)

    def predict(self, X):
        """return the mean"""
        return np.tile(self.mean, (X.shape[0], 1))


class LagWrapper(BaseEstimator, TransformerMixin):

    """Wraps a scikit-learn model, lags the data, and deals with NAs."""

    partial_data_ok = True

    def __init__(self, model, periods=1, freq='30min'):
        """Lags a dataset.

        Lags all features.
        Missing data is dropped for fitting, and replaced with the mean for predict.

        :periods: Number of timesteps to lag by
        """
        assert isinstance(model, BaseEstimator), "`model` isn't a scikit-learn model"

        BaseEstimator.__init__(self)
        TransformerMixin.__init__(self)

        self.periods = periods
        self.freq = freq

        self.model = model

    def fit(self, X, y=None):
        """Fit the model with X

        compute number of output features

        :X: pandas dataframe
        :y: Pandas dataframe or series
        """
        if 'site' in X.columns:
            raise ValueError("site should be an index, not a column")

        self.n_features = X.shape[1]
        self.n_outputs = y.shape[1]

        self.X_mean = X.mean()
        self.X_cols = X.columns

        X_lag = self.transform(X, nans='drop')

        logger.info("LW: Data lagged, fitting with {nk} samples out of {nx}".format(nk=X_lag.shape[0], nx=X.shape[0]))

        self.model.fit(X_lag, y.ix[X_lag.index])

        return self

    def lag_dataframe(self, df, grouping=None, lagged_only=False, variables=None):
        """Helper for lagging a dataframe

        :df: Pandas dataframe with a time index
        :returns: Dataframe with all columns copied and lagged

        """
        df = pd.DataFrame(df)
        if not all(df.dtypes == 'float64'):
            raise ValueError('One or more columns are non-numeric.')

        if variables is None:
            shifted = df
        else:
            shifted = df[variables]

        if grouping is not None:
            shifted = (shifted.reset_index(grouping)
                              .groupby(grouping)
                              .shift(self.periods, self.freq)
                              .reset_index(grouping, drop=True)
                              .set_index(grouping, append=True))
            # it would be nice to do this, but https://github.com/pydata/pandas/issues/114524
            # shifted = df.groupby(level=grouping).shift(self.periods, self.freq)
        else:
            shifted = shifted.shift(self.periods, self.freq)
        shifted.columns = [c + '_lag' for c in shifted.columns]

        if lagged_only:
            return shifted.ix[df.index]
        else:
            return df.join(shifted)

    def fix_nans(self, lagged_df, nans=None):
        """Remove NAs, replace with mean, or do nothing

        :df: Pandas dataframe
        :nans: 'drop' to drop NAs, 'fill' to fill with mean values, None to leave NAs in place.
        :returns: Dataframe with NANs modified

        """
        if nans == 'drop':
            return lagged_df.dropna()
        elif nans == 'fill':
            # Replace NAs in lagged columns with mean values from fitting step
            replace = {c + '_lag': {np.nan: self.X_mean[c]} for c in self.X_cols}
            if hasattr(self, 'y_cols'):
                replace.update({c + '_lag': {np.nan: self.y_mean[c]} for c in self.y_cols})
            lagged_df.replace(replace, inplace=True)
            return lagged_df
        else:
            # return with NAs
            return lagged_df

    def transform(self, X, nans=None):
        """Add lagged features to X

        :X: Dataframe matching the fit frame.
        :nans: 'drop' to drop NAs, 'fill' to fill with mean values, None to leave NAs in place.
        :returns: Dataframe with lagged duplicate columns

        """
        check_is_fitted(self, ['n_features', 'n_outputs'])

        n_samples, n_features = X.shape

        if n_features != self.n_features:
            raise ValueError("X shape does not match training shape")

        if 'site' in X.index.names:
            X_lag = self.lag_dataframe(X, grouping='site')
        else:
            X_lag = self.lag_dataframe(X)

        return self.fix_nans(X_lag, nans)

    def predict(self, X):
        """Predicts with a model using lagged X

        :X: Dataframe matching the fit dataframe
        :returns: prediction based on X
        """

        X_lag = self.transform(X, nans='fill')

        logger.info("Data lagged, now predicting.")

        return self.model.predict(X_lag)


class MarkovWrapper(LagWrapper):
    """Wraps a scikit-learn model, Markov-lags the data (includes y values), and deals with NAs."""

    partial_data_ok = True

    def __init__(self, model, periods=1, freq='30min', lag_X=True):
        """Markov lagged dataset

        :periods: Number of timesteps to lag by
        """
        super(self.__class__, self).__init__(model, periods, freq)

        self.lag_X = lag_X

    def fit(self, X, y):
        """Fit the model with X

        compute number of output features

        :X: pandas dataframe
        :y: Pandas dataframe or series
        """
        if 'site' in X.columns:
            raise ValueError("site should be an index, not a column")

        self.n_features = X.shape[1]
        self.n_outputs = y.shape[1]

        self.X_mean = X.mean()
        self.X_cols = X.columns

        self.y_mean = y.mean()
        self.y_cols = y.columns

        X_lag = self.transform(X, y, nans='drop')

        logger.info("MW: Data lagged, fitting with {nk} samples out of {nx}".format(nk=X_lag.shape[0], nx=X.shape[0]))

        self.model.fit(X_lag, y.ix[X_lag.index])

        return self

    def transform(self, X, y=None, nans=None):
        """Add lagged features of X and y to X

        :X: features dataframe
        :y: outputs dataframe
        :nans: 'drop' to drop NAs, 'fill' to fill with mean values, None to leave NAs in place.
        :returns: X dataframe with X and y lagged columns

        """
        check_is_fitted(self, ['n_features', 'n_outputs'])

        n_samples, n_features = X.shape

        if n_features != self.n_features:
            raise ValueError("X shape does not match training shape")

        if 'site' in X.index.names:
            grouping = 'site'
        else:
            grouping = None

        if self.lag_X:
            X_lag = self.lag_dataframe(X, grouping=grouping)
        else:
            X_lag = X

        if y is not None:
            y_lag = self.lag_dataframe(y, grouping=grouping, lagged_only=True)
            X_lag = pd.merge(X_lag, y_lag, how='left', left_index=True, right_index=True)

        return self.fix_nans(X_lag, nans)

    def predict(self, X):
        """Predicts with a model using lagged X

        :X: Dataframe matching the fit frame
        :returns: Dataframe of predictions
        """

        X_lag = self.transform(X, nans='fill')

        logger.info("Data lagged, now predicting, step by step.")

        # initialise with mean y values
        init = pd.concat([X_lag.iloc[0], self.y_mean]).reshape(1, -1)
        results = []
        results.append(self.model.predict(init).ravel())
        n_steps = X_lag.shape[0]
        logger.info('Predicting, step 0 of {n}'.format(n=n_steps), end='\r')

        for i in range(1, n_steps):
            if i % 100 == 0:
                logger.info('Predicting, step {i} of {n}'.format(i=i, n=n_steps), end="\r")
            x = np.concatenate([X_lag.iloc[i], results[i - 1]]).reshape(1, -1)
            results.append(self.model.predict(x).ravel())
        logger.info('Predicting, step {i} of {n}'.format(i=n_steps, n=n_steps))

        # results = pd.DataFrame.from_records(results, index=X_lag.index, columns=self.y_cols)
        # Scikit-learn models produce numpy arrays, not pandas dataframes
        results = np.concatenate(results)

        return results


class LagAverageWrapper(BaseEstimator):

    """Modelwrapper that lags takes Tair, SWdown, RelHum, Wind, and Rainf, and lags them to estimate Qle fluxes."""

    partial_data_ok = True

    def __init__(self, var_lags, model, datafreq=0.5):
        """Model wrapper

        :var_lags: OrderedDict like {'Tair': ['cur', '2d'], 'Rainf': ['cur', '2h', '7d', '30d', ...
        :model: model to use lagged variables with
        :datafreq: data frequency in hours

        """
        self.var_lags = var_lags
        self.model = model
        self.datafreq = datafreq

    def _lag_array(self, X, var_lags, datafreq):
        """Lags the input array according to the lags specified in var_lags

        :X: array with columns matching var_lags
        :returns: array with original and lagged averaged variables

        """
        lagged_data = []
        for i, v in enumerate(var_lags):
            for l in var_lags[v]:
                if l == 'cur':
                    lagged_data.append(X[:, [i]])
                else:
                    if l.endswith('M'):
                        # Lagged variable minus original variable
                        lag_avg = rolling_mean(X[:, [i]], l[:-1], datafreq=datafreq, shift=1)
                        lagged_data.append(lag_avg - X[:, [i]])
                    else:
                        lag_avg = rolling_mean(X[:, [i]], l, datafreq=datafreq, shift=1)
                        lagged_data.append(lag_avg)
        return np.concatenate(lagged_data, axis=1)

    def _lag_data(self, X, var_lags=None, datafreq=None):
        """lag an array. Assumes that each column corresponds to variables listed in lags

        :X: dataframe or ndarray
        :datafreq: array data rate in hours
        :returns: array of lagged averaged variables

         if var_lags is None:
            var_lags = self.var_lags
        if datafreq is None:
            self.datafreq

       """
        if var_lags is None:
            var_lags = self.var_lags
        if datafreq is None:
            datafreq = self.datafreq

        if isinstance(X, pd.DataFrame):
            assert all([v in X.columns for v in var_lags]), "Variables in X do not match initialised var_lags"
            columns = ["%s_%s" % (k, v) for k, l in var_lags.items() for v in l]
            if 'site' in X.index.names:
                # split-apply-combine by site
                results = {}
                for site in X.index.get_level_values('site').unique():
                    results[site] = self._lag_array(X.ix[X.index.get_level_values('site') == site, list(var_lags)].values, var_lags, datafreq)
                result = np.concatenate([d for d in results.values()])
            else:
                result = self._lag_array(X[list(var_lags)].values, var_lags, datafreq)
            result = pd.DataFrame(result, index=X.index, columns=columns)
        elif isinstance(X, np.ndarray) or isinstance(X, xr.DataArray):
            # we have to assume that the variables are given in the right order
            assert (X.shape[1] == len(var_lags))
            if isinstance(X, xr.DataArray):
                result = self._lag_array(np.array(X), var_lags, datafreq)
            else:
                result = self._lag_array(X, var_lags, datafreq)

        return result

    def fit(self, X, y, datafreq=None):
        """fit model using X

        :X: Dataframe, or ndarray with len(var_lags) columns
        :y: frame/array with columns to predict

        """
        if datafreq is None:
            datafreq = self.datafreq

        lagged_data = self._lag_data(X, datafreq=datafreq)

        # store mean for filling empty values on predict
        self._means = np.nanmean(lagged_data, axis=0)

        fit_idx = np.isfinite(lagged_data).all(axis=1)

        logger.info("LAW: Data lagged, fitting with {nk} samples out of {nx}".format(nk=sum(fit_idx), nx=X.shape[0]))

        self.model.fit(lagged_data[fit_idx], y[fit_idx])

    def predict(self, X, datafreq=None):
        """predict model using X

        :X: Dataframe or ndarray of similar shape
        :returns: array like y

        """
        if datafreq is None:
            datafreq = self.datafreq

        if any(X.isnull()):
            raise ValueError("Can't predict with NAs in X - check your data.")

        lagged_data = self._lag_data(X, datafreq=datafreq)

        # fill initial NaN values with mean values
        for i in range(lagged_data.shape[1]):
            lagged_data.ix[np.isnan(lagged_data.iloc[:, i]), i] = self._means[i]

        return self.model.predict(lagged_data)


class MarkovLagAverageWrapper(LagAverageWrapper):
    """Lags variables, and uses markov fitting when fluxes are included"""

    partial_data_ok = True

    def __init__(self, var_lags, model, datafreq=0.5):
        super().__init__(var_lags, model, datafreq)
        self._x_vars = []
        self._x_lags = OrderedDict()
        self._y_vars = []
        self._y_lags = OrderedDict()
        for k, v in var_lags.items():
            if k in ['Qle', 'Qh', 'NEE', 'Rnet', 'Qg']:
                self._y_vars.append(k)
                self._y_lags[k] = v
            else:
                self._x_vars.append(k)
                self._x_lags[k] = v
        self._n_y_lags = np.sum([len(lags) for lags in self._y_lags.values()])
        self._n_x_lags = np.sum([len(lags) for lags in self._x_lags.values()])

    def fit(self, X, y, datafreq=None):
        if isinstance(X, pd.DataFrame):
            assert all(X.columns == list(self._x_vars))
        else:  # Assume we're being passed stuff innthe right order
            assert X.shape[1] == len(self._x_vars)

        assert isinstance(y, pd.DataFrame), "Require dataframe input for y"
        assert all([v in y.columns for v in list(self._y_vars)]), "Lagged flux is missing from input"

        self._y_cols = list(y.columns)

        X_fit = pd.concat([X, y], axis=1)

        super().fit(X_fit, y, datafreq)

    def _lag_mean(self, results_list, idx, lag, datafreq):
        timesteps = window_to_rows(lag, datafreq)
        if timesteps < len(results_list):
            timesteps = len(results_list)  # Use all steps
        return np.mean([r[idx] for r in results_list[-timesteps:]])

    def predict(self, X, datafreq=None):
        if datafreq is None:
            datafreq = self.datafreq

        X_lag = self._lag_data(X, self._x_lags)

        logger.info("Data lagged, now predicting, step by step.")

        # initialise with mean y values
        init = np.concatenate([X_lag.iloc[[0]], np.full([1, self._n_y_lags], np.nan)], axis=1)
        # take means where nans exist
        init = np.where(np.isfinite(init), init, self._means)
        results = []
        results.append(self.model.predict(init).ravel())
        n_steps = X_lag.shape[0]
        logger.info('Predicting, step 0 of {n}'.format(n=n_steps), end='\r')

        for i in range(1, n_steps):
            if i % 100 == 0:
                logger.info('Predicting, step {i} of {n}'.format(i=i, n=n_steps), end="\r")
            # TODO: Averaging of past fluxes may need efficiency gains
            last_result = []
            for v in self._y_lags:
                idx = self._y_cols.index(v)
                for l in self._y_lags[v]:
                    last_result.append(self._lag_mean(results, idx, l, datafreq))
            last_result = np.array(last_result, ndmin=2)
            x = np.concatenate([X_lag.iloc[[i]], last_result], axis=1)
            results.append(self.model.predict(x).ravel())
        logger.info('Predicting, step {i} of {n}'.format(i=n_steps, n=n_steps))

        results = pd.DataFrame.from_records(results, index=X.index, columns=self._y_cols)
        # Scikit-learn models produce numpy arrays, not pandas dataframes
        # results = np.stack(results)

        return results


class MissingDataWrapper(BaseEstimator):

    """Model wrapper that kills NAs"""

    partial_data_ok = True

    def __init__(self, model):
        """kills NAs

        :model: scikit-learn style model to wrap

        """
        self.model = model

    def fit(self, X, y):
        """Removes NAs, then fits

        :X: Numpy array-like
        :y: Numpy array-like
        """
        qc_index = (np.all(np.isfinite(X), axis=1, keepdims=True) &
                    np.all(np.isfinite(y), axis=1, keepdims=True)).ravel()

        logger.info("MDW: Dropping data... using {n} samples of {N}".format(
            n=qc_index.sum(), N=X.shape[0]))
        # make work with arrays and dataframes
        self.model.fit(X[qc_index], y[qc_index])

    def predict(self, X):
        """pass on model prediction

        :X: numpy array-like
        :returns: numpy array like y

        """
        return self.model.predict(X)


#########################################
# Helper functions
#########################################

def rolling_window(a, rows):
    """from http://www.rigtorp.se/2011/01/01/rolling-statistics-numpy.html"""
    shape = a.shape[:-1] + (a.shape[-1] - rows + 1, rows)
    strides = a.strides + (a.strides[-1],)
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)


def window_to_rows(window, datafreq=0.5):
    """calculate number of rows for window

    :window: window of the format "30min", "3h"
    :datafreq: data frequency in hours
    :returns: number of rows

    """
    n, freq = re.match('(\d*)([a-zA-Z]*)', window).groups()
    n = int(n)
    if freq == "min":
        rows = n / (60 * datafreq)
    elif freq == "h":
        rows = n / datafreq
    elif freq == "d":
        rows = n * 24 / datafreq
    else:
        raise 'Unknown frequency "%s"' % freq

    assert rows == int(rows), "window doesn't match data frequency - not integral result"

    return int(rows)


def rolling_mean(data, window, datafreq=0.5, shift=0):
    """calculate rolling mean for an array

    :data: ndarray
    :window: time span, e.g. "30min", "2h"
    :datafreq: data frequency in hours
    :shift: number of time-steps to skip (0 for inclusive mean, 1 for exclusive mean)
    :returns: data in the same shape as the original, with leading NaNs
    """
    rows = window_to_rows(window, datafreq)

    result = np.full_like(data, np.nan)

    if shift > 0:
        np.mean(rolling_window(data[:(-shift), ].T, rows), -1, out=result[(rows - 1 + shift):, :].T)
    else:
        assert shift == 0, "TODO: negative shifts not implemented"
        np.mean(rolling_window(data.T, rows), -1, out=result[(rows - 1):, :].T)
    return result


def get_lags():
    """Gets standard lag times """
    lags = [('30min'),
            ('1h'), ('2h'), ('3h'), ('4h'), ('5h'), ('6h'), ('12h'),
            ('1d'), ('2d'), ('3d'), ('5d'), ('7d'), ('14d'),
            ('30d'), ('60d'), ('90d'), ('180d'), ('365d')]
    return lags


def dropna(array):
    """like pandas.dropna, but for arrays"""

    return array[np.isfinite(array).all(axis=1)]
