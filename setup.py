from setuptools import setup

setup(
    name="container-prefab",
    description="Build container images faster ⚡️",
    long_description=open("README.md").read(),
    author="Lex Scarisbrick",
    author_email="lex@scarisbrick.org",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    python_requires=">=3.7",
    url="https://github.com/lexsca/prefab.git",
    package_dir={"": "lib"},
    packages=["prefab", "prefab.image"],
    scripts=["bin/prefab"],
    install_requires=["docker", "pyyaml"],
)
