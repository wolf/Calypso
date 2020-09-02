from setuptools import setup, find_packages


with open("README.md", "r") as f:
    readme = f.read()


setup(
    name="calypso",
    version="0.1.0",
    description="Literate Programming Tool",
    long_description=readme,
    author="Wolf",
    author_email="Wolf@zv.cx",
    url="",
    license="",
    packages=find_packages(exclude=("tests", "sample-output")),
)
