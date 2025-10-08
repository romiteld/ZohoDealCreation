"""
Well Shared Library - Common utilities for Well Intake API ecosystem.

Shared across:
- Well Intake API (main email processing)
- Teams Bot (Microsoft Teams integration)
- Vault Agent (weekly digest generation)
"""

from setuptools import setup, find_packages

setup(
    name="well_shared",
    version="0.1.0",
    description="Shared utilities for Well Intake API services",
    author="The Well Team",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "asyncpg>=0.29.0",
        "redis>=5.0.0",
        "azure-communication-email>=1.0.0",
        "azure-identity>=1.15.0",
        "azure-keyvault-secrets>=4.7.0",
        "openai>=1.12.0",
        "pydantic>=2.5.0",
        "httpx>=0.26.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
    ],
)
