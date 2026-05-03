from setuptools import setup, find_packages

setup(
    name="dictselect",
    version="0.1.0",
    description="A lazy selector for nested Python data structures.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="alphacena",
    author_email="lukas.makswitis@gmail.com",
    license="MIT",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests*"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)