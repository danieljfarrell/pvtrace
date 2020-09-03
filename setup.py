from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

with open("pvtrace/__init__.py", "r") as fp:
    # binds local __version__ to the line that look like  "__version__ = '2.1.3'"
    exec(next(line for line in fp if "__version__" in line))

setup(
    name="pvtrace",
    version=__version__,
    description="Optical ray tracing for luminescent materials and spectral converter photovoltaic devices.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Daniel Farrell",
    author_email="dan@excitonlabs.com",
    url="https://github.com/danieljfarrell/pvtrace",
    download_url="https://github.com/danieljfarrell/pvtrace/archive/{}.tar.gz".format(
        __version__
    ),
    python_requires=">=3.7.2,<3.8",
    packages=find_packages(),
    keywords=["optics", "raytracing", "photovoltaics", "energy"],
    install_requires=["numpy", "pandas", "anytree", "meshcat>=0.0.16", "trimesh[easy]"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Scientific/Engineering :: Visualization",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.7",
    ],
)
