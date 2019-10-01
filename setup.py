"""Setup script for odin_devices python package."""

# import sys
from setuptools import setup, find_packages
import versioneer

required = []

setup(name='odin_devices',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='Odin Device Drivers',
      url='https://github.com/stfc-aeg/odin-devices',
      author='Adam Neaves',
      author_email='adam.neaves@stfc.ac.uk',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      install_requires=required,
      extras_require={
          'test': ['nose', 'coverage', 'mock']
      }
      )
