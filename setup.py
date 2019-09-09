"""Setup script for odin_devices python package."""

# import sys
from setuptools import setup, find_packages
import versioneer

with open('requirements.txt') as f:
    required = f.read().splitlines()

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
      zip_safe=False
      )
