# Prefab

### *Build container images faster* ⚡️

[![https://xkcd.com/303/](https://imgs.xkcd.com/comics/compiling.png)](https://xkcd.com/license.html "https://xkcd.com/303/")

[![shields.io](https://img.shields.io/pypi/pyversions/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![shields.io](https://img.shields.io/pypi/v/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![shields.io](https://img.shields.io/pypi/wheel/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![readthedocs.org](https://readthedocs.org/projects/prefab/badge/?version=stable)](https://prefab.readthedocs.io/en/stable/?badge=stable) [![coveralls.io](https://coveralls.io/repos/github/lexsca/prefab/badge.svg?branch=main)](https://coveralls.io/github/lexsca/prefab?branch=main) [![shields.io](https://img.shields.io/github/license/lexsca/prefab.svg)](https://github.com/lexsca/prefab/blob/master/LICENSE) [![shields.io](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


A variation of the above [xkcd webcomic](https://xkcd.com/303/) might be, "containers are building!"  If it takes way too long to build your containers, *Prefab* might be able to help!

*Prefab* is a Python-based container image build tool that uses deterministic remote caching to reduce build times. Unlike [BuildKit](https://github.com/moby/buildkit#cache) and the [Docker CLI](https://docs.docker.com/engine/reference/commandline/build/#specifying-external-cache-sources), which use container layer caching, *Prefab* caches based on a digest of the Dockerfile in combination with digests of specified files and directory trees.  This allows *Prefab* to check for and pull cached images before resorting to building a new image.

## Quickstart

This is a simple example of a Python app which has package dependencies that take several minutes to compile.  After the first run of *Prefab*, subsequent runs will take substantially less time.  More importantly, the cache can be pushed to an image repository as an ordinary container image.  Clone this repo, or copy files from the [example directory](https://github.com/lexsca/prefab/tree/main/example) to build the example app.

To run *prefab* as a container to build the example app in a linux or mac terminal:


```
docker run --rm -v `pwd`:/build -w /build \
    -v /var/run/docker.sock:/var/run/docker.sock 
    quay.io/lexsca/prefab:dood 
    --repo quay.io/lexsca/example --target app:app

```

To run *Prefab* as a Python package to build the example app:

```
pip3 install container-prefab
prefab --repo quay.io/lexsca/example --target app:app
```
