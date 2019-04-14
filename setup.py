from setuptools import setup

setup(
   name='pvtrace',
   version='2.0',
   description='Optical ray tracing for photovoltaic devices and luminescent materials',
   author='Daniel Farrell',
   author_email='dan@excitonlabs.com',
   packages=['src/pvtrace'],
   python_requires='>=3.7.2',
   install_requires=[
       "numpy",
       "scipy",
       "pandas",
       "anytree",
       "meshcat>=0.0.16",
       "trimesh"
   ]
)