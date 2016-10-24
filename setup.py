from setuptools import find_packages, setup

import django_c3


setup(
    name='django-c3',
    version=django_c3.__version__,
    description=django_c3.__doc__,
    long_description=open('README.rst').read(),
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
    author='Zach Mathew',
    url='http://github.com/czpython/django-c3',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
