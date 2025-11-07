from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="legal-document-splitter",
    version="1.0.0",
    author="Danila Permogorskii",
    description="FastAPI service for splitting Russian legal documents into articles with NLP metadata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/danila-permogorskii/legal-document-splitter",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "python-multipart==0.0.6",
        "pydantic==2.5.0",
        "python-docx==1.1.0",
        "pdfplumber==0.10.3",
        "spacy==3.7.2",
        "langchain==0.1.0",
    ],
    entry_points={
        "console_scripts": [
            "legal-doc-splitter=legal_doc_splitter.main:main",
        ],
    },
)
