from setuptools import setup, find_packages

setup(
    name="pySystemTest",
    version="1.0.0",
    packages=find_packages(),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.28",
        "PyYAML>=6.0",
        "jsonpath-ng>=1.5.3",
        "Jinja2>=3.0"
    ],
    entry_points={
        "console_scripts": [
            "pySystemTest=api_tester:main_cli",
        ],
    },
)