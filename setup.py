from setuptools import setup, find_packages

setup(
    name="fitbit-ai-poc",
    version="0.1.0",
    description="Fitbit Conversational AI Proof of Concept",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires="^>=3.9",
    install_requires=[
        "langgraph^>=0.0.40",
        "langchain^>=0.1.0",
        "anthropic^>=0.7.0",
        "psycopg2-binary^>=2.9.0",
        "sqlalchemy^>=2.0.0",
        "pandas^>=2.0.0",
        "requests^>=2.31.0",
        "python-dotenv^>=1.0.0",
    ],
)
