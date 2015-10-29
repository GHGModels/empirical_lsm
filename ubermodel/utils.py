#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: utils.py
Author: ned haughton
Email: ned@nedhaughton.com
Github: https://github.com/naught101
Description: ubermodel helper functions
"""


def print_good(string, kwargs={}):
    """print string in green
    """
    okgreen = '\033[92m'
    reset = '\033[39m'

    print(okgreen + string + reset, **kwargs)


def print_warn(string, kwargs={}):
    """print string in yellow
    """
    warnyellow = '\033[93m'
    reset = '\033[39m'

    print(warnyellow + string + reset, **kwargs)


def print_bad(string, kwargs={}):
    """print string in red
    """
    badred = '\033[91m'
    reset = '\033[39m'

    print(badred + string + reset, **kwargs)
