from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in zatca/__init__.py
from zatca import __version__ as version

setup(
	name="zatca",
	version=version,
	description="integration Zakat, Tax and Customs Authority to E-invoicing",
	author="baha Slnee",
	author_email="baha@slnee.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
