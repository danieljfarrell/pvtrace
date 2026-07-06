"""Build the native tracing kernel in-place.

Usage::

    python -m pvtrace.engine.build

Uses OpenMP when a toolchain is available (on macOS install it with
``brew install libomp``); otherwise builds a serial kernel, which still
runs but uses a single thread.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent


def _openmp_args():
    if sys.platform == "darwin":
        for prefix in ("/opt/homebrew/opt/libomp", "/usr/local/opt/libomp"):
            if os.path.exists(prefix):
                compile_args = [
                    "-O3",
                    "-Xpreprocessor",
                    "-fopenmp",
                    f"-I{prefix}/include",
                ]
                link_args = [f"-L{prefix}/lib", "-lomp"]
                return compile_args, link_args
        return ["-O3"], []
    if sys.platform.startswith("win"):
        return ["/O2", "/openmp"], []
    return ["-O3", "-fopenmp"], ["-fopenmp"]


def build(verbose=True):
    import numpy
    from Cython.Build import cythonize
    from setuptools import Extension
    from setuptools.command.build_ext import build_ext
    from setuptools.dist import Distribution

    compile_args, link_args = _openmp_args()
    if verbose:
        print(f"Compile args: {compile_args}")
        print(f"Link args: {link_args}")

    extension = Extension(
        "pvtrace.engine._kernel",
        [str(HERE / "_kernel.pyx")],
        include_dirs=[numpy.get_include()],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
    )

    cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        dist = Distribution(
            {"ext_modules": cythonize([extension], language_level=3)}
        )
        cmd = build_ext(dist)
        cmd.inplace = True
        cmd.ensure_finalized()
        cmd.run()
    finally:
        os.chdir(cwd)
    if verbose:
        print("Engine kernel built.")


if __name__ == "__main__":
    build()
