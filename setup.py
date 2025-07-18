from setuptools import setup, find_packages

setup(
    name="sanchalak",
    version="0.1.0",
    description="Unified government scheme eligibility system (EFR, scheme server, schemabot)",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
    include_package_data=True,
    python_requires=">=3.8",
) 