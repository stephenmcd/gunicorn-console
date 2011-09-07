
from setuptools import setup


setup(
    name="gunicorn-console",
    version=__import__("gunicorn_console").__version__,
    author="Stephen McDonald",
    author_email="stephen.mc@gmail.com",
    description="A curses application for managing gunicorn processes.",
    long_description=open("README.rst").read(),
    license="BSD",
    url="http://github.com/stephenmcd/gunicorn-console/",
    py_modules=["gunicorn_console",],
    install_requires=["setproctitle", "sphinx-me"],
    entry_points="""
        [console_scripts]
        gunicorn-console=gunicorn_console:main
    """,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console :: Curses",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Server",
    ]
)
