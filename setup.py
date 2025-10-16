from setuptools import setup, find_packages

setup(
    name="agent_16Oct",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-adk",
        "aiohttp>=3.8.0",
    ],
    python_requires=">=3.8",
)
