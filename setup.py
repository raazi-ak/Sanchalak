from setuptools import setup, find_packages
import os

# Read requirements from requirements.txt
def read_requirements(filename):
    with open(filename, 'r') as f:
        requirements = []
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('-r'):
                # Remove version constraints for setup.py
                if '==' in line:
                    package = line.split('==')[0]
                elif '>=' in line:
                    package = line.split('>=')[0]
                elif '<=' in line:
                    package = line.split('<=')[0]
                else:
                    package = line
                requirements.append(package)
    return requirements

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'SANCHALAK_README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Unified government scheme eligibility system (EFR, scheme server, schemabot)"

setup(
    name="sanchalak",
    version="0.1.0",
    description="Unified government scheme eligibility system (EFR, scheme server, schemabot)",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="AnnamAI Team",
    author_email="team@annamai.com",
    url="https://github.com/raazi-ak/Sanchalak",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("requirements-dev.txt"),
        "efr": [
            "fastapi",
            "uvicorn[standard]",
            "pymongo",
            "sqlalchemy",
            "alembic",
            "psycopg2-binary",
        ],
        "schemabot": [
            "fastapi",
            "uvicorn[standard]",
            "langchain",
            "langchain-anthropic",
            "langchain-openai",
            "pydantic",
            "redis",
            "structlog",
        ],
        "translation": [
            "fastapi",
            "uvicorn",
            "httpx",
            "pydantic",
            "python-multipart",
        ],
    },
    include_package_data=True,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="government schemes eligibility AI ML NLP",
    project_urls={
        "Bug Reports": "https://github.com/raazi-ak/Sanchalak/issues",
        "Source": "https://github.com/raazi-ak/Sanchalak",
        "Documentation": "https://github.com/raazi-ak/Sanchalak/blob/main/SANCHALAK_README.md",
    },
) 