# Adapted from https://github.com/pypa/sampleproject/blob/60d85f505adab230b8060a19d5841351e5a41bed/setup.py
from setuptools import setup, find_packages
from os import path

setup(
    name='saltstack_exporter',
    version='0.0.8',

    description='Prometheus exporter for Saltstack minions',
    url='https://github.com/BonnierNews/saltstack_exporter',
    author='BonnierNews',
    author_email='',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: System Administrators',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
    keywords='saltstack prometheus',

    packages=['saltstack_exporter'],
    install_requires=['prometheus_client>=0.0.18', 'tornado>=6,<7'],
    extras_require={
        'dev': [],
        'test': [],
    },

    entry_points={
        'console_scripts': [
            'saltstack_exporter=saltstack_exporter.exporter:main',
        ],
    },
)
