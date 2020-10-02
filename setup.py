from setuptools import setup

setup(
    name="container-prefab",
    description="Efficiently build container images",
    # long_description=open('README.rst').read(),
    author="Lex Scarisbrick",
    author_email="lex@scarisbrick.org",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3.8",
    ],
    python_requires=">=3.8",
    url="https://github.com/lexsca/prefab.git",
    package_dir={"": "lib"},
    packages=["prefab"],
    scripts=["bin/container-prefab"],
    install_requires=["docker", "pyyaml"],
)
