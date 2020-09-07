from setuptools import setup, find_packages  # type: ignore


with open("README.md", "r") as f:
    readme = f.read()


setup(
    name="blue",
    version="0.2.0",
    description="Literate Programming Tool",
    long_description=readme,
    author="Wolf",
    author_email="Wolf@zv.cx",
    url="",
    license="",
    packages=find_packages(exclude=("tests", "sample-output")),
    entry_points="""
        [console_scripts]
        blue=blue.blue:blue
    """
)
