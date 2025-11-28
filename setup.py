from setuptools import setup, find_packages

setup(
    name="devo",
    version="0.1.0",
    description="DEVO: Data Enrichment and Validation Operator (iCSV + Frictionless)",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    packages=find_packages(exclude=("tests",)),
    python_requires=">=3.8",
    install_requires=[
        "frictionless>=4.0.0",
        "psycopg2-binary>=2.9.0",
        "pytest>=7.0.0",
        "python-dateutil>=2.8.0",
        "pyyaml>=5.4.1",
    ],
    entry_points={
        "console_scripts": [
            "devo=devo.cli:main",
        ]
    },
    include_package_data=True,
    license="MIT",
)
