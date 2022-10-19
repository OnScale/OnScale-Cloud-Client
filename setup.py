import os
import re
from setuptools import setup, find_packages

DIRNAME = os.path.dirname(os.path.abspath(__file__))


def get_requirements(requirements_file):
    """Get requirements from the requirements.txt"""
    dirname = os.path.dirname(os.path.realpath(__file__))
    requirements_file = os.path.join(dirname, requirements_file)
    with open(requirements_file, "r") as f:
        requirements = f.read().splitlines()
    return requirements


def get_version():
    """Get version from onscale./__init__.py"""
    init_file = os.path.join(DIRNAME, "onscale_client", "__init__.py")
    pattern = re.compile(r"__version__\s=\s\"(\d+\.\d+\.\d+)\"")
    version = None
    with open(init_file, "r") as f:
        while True:
            line = f.readline().strip()
            if not line:
                break
            match = pattern.search(line)
            if match:
                version = match[1]
                break
    if version is None:
        raise AttributeError("Could not locate __version__ for onscale")
    return version


setup(
    name="onscale_client",
    version=get_version(),
    description="API for accessing the OnScale cloud platform",
    python_requires=">=3.7",
    url="https://github.com/OnScale/Simulation_API/packages/cloud_client",
    packages=find_packages(exclude=["examples", "tests", "scripts"]),
    install_requires=get_requirements("requirements.txt"),
    extras_require={
        "onscale": ["onscale"],
        "dev": [
            "pytest",
            "flake8",
            "mypy",
            "sphinx",
            "sphinx-autodoc-typehints",
            "sphinx_autodoc_future_annotations",
        ],
    },
)
