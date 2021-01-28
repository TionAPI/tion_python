from __future__ import print_function
from setuptools import setup, find_packages
import os


here = os.path.abspath(os.path.dirname(__file__))

setup(
    name='tion_btle',
    version='%%%VERSION%%%',
    long_description="Module for working with Tion breezers",
    url='https://github.com/TionAPI/tion_python/tree/dev',
    install_requires=['bluepy==1.3.0'],
    description='Python module for interacting with Tion breezers',
    packages=find_packages(),
)
