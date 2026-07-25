from setuptools import setup, find_packages

setup(
    name="nl2bi",
    version="0.1.1",
    description="Natural Language to Business Intelligence - Convert natural language queries to SQL, charts, and business insights",
    author="Mithran Bala",
    author_email="mithranbala123@gmail.com",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "openai>=1.0.0",
        "sqlalchemy>=2.0.0",
        "pandas>=1.5.0",
        "langchain>=0.1.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "llm": [
            "anthropic>=0.7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "nl2bi=nl2bi.cli:main",
        ],
    },
)
