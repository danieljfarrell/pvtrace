from setuptools import setup, find_packages

setup(
   name='pvtrace',
   version='2.0',
   description='Optical ray tracing for luminescent materials and spectral converter photovoltaic devices.',
   author='Daniel Farrell',
   author_email='dan@excitonlabs.com',
   python_requires='>=3.7.2',
   packages=find_packages(),
   install_requires=[
       "numpy",
       "scipy",
       "pandas",
       "anytree",
       "meshcat>=0.0.16",
       "trimesh[easy]"
   ]
)