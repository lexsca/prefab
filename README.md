# Prefab

### *Build container images faster* ⚡️

[![https://xkcd.com/303/](https://imgs.xkcd.com/comics/compiling.png)](https://xkcd.com/license.html "https://xkcd.com/303/")

[![shields.io](https://img.shields.io/pypi/pyversions/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![shields.io](https://img.shields.io/pypi/v/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![shields.io](https://img.shields.io/pypi/wheel/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![readthedocs.org](https://readthedocs.org/projects/prefab/badge/?version=stable)](https://prefab.readthedocs.io/en/stable/?badge=stable) [![coveralls.io](https://coveralls.io/repos/github/lexsca/prefab/badge.svg?branch=main)](https://coveralls.io/github/lexsca/prefab?branch=main) [![shields.io](https://img.shields.io/github/license/lexsca/prefab.svg)](https://github.com/lexsca/prefab/blob/master/LICENSE) [![shields.io](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


*Prefab* is a Python-based container image build tool that uses deterministic remote caching to reduce build times.

Unlike [BuildKit](https://github.com/moby/buildkit#cache) and the [Docker CLI](https://docs.docker.com/engine/reference/commandline/build/#specifying-external-cache-sources), which use build layer caching, *Prefab* uses whole image caching based on a digest of the Dockerfile in combination with digests of specified files and directory trees.  This allows *Prefab* to check for and pull cached images before resorting to building a new image.


## Quickstart

Look at the [example directory](https://github.com/lexsca/prefab/tree/main/example) to see how to build an example app with *Prefab*.


## Installation and usage

*Prefab* can be installed and run in three different ways:

1. Local Python package
1. Docker outside of Docker (DooD) container
1. Docker in Docker (DinD) container

Use whichever mode works best for the use-case(s) at hand.  Each supports the same CLI arguments:  

#### CLI arguments

```
usage: prefab [-h] [--config PATH] [--dry-run] [--force] [--monochrome]
              [--push TARGET_NAME [TARGET_NAME ...]] --repo URI --target
              TARGET_NAME[:TAG] [TARGET_NAME[:TAG] ...]

Build container images faster ⚡️

optional arguments:
  -h, --help            show this help message and exit
  --config PATH, -c PATH
                        Target build config file to use (default: prefab.yml)
  --dry-run             Show how targets would be built (implies --force)
  --force               Force target(s) to be rebuilt
  --monochrome, -m      Don't colorize log messages
  --push TARGET_NAME [TARGET_NAME ...], -p TARGET_NAME [TARGET_NAME ...]
                        Image target(s) to push to repo after building
  --repo URI, -r URI    Image repo to use (e.g. quay.io/lexsca/prefab)
  --target TARGET_NAME[:TAG] [TARGET_NAME[:TAG] ...], -t TARGET_NAME[:TAG] [TARGET_NAME[:TAG] ...]
                        Image target(s) to build with optional custom image
                        tag
```

#### Local Python package

To install *Prefab* as a local Python package:

```
pip install container-prefab
```

To run *Prefab* as a local Python package to build an push a build target:

```
prefab --repo repo.tld/org/project --push --target name
```

#### Docker outside of Docker (DooD)

To get the *Prefab* Docker outside of Docker (DooD) image:

```
docker pull quay.io/lexsca/prefab:dood
```

To run the *Prefab* Docker outside of Docker image to build an push a build target:

```
docker run --rm -it -v $(/bin/pwd):/build -w /build \
    -e REGISTRY_AUTH=$(jq -c . ~/.docker/config.json | base64) \
    -v /var/run/docker.sock:/docker.sock \                
    quay.io/lexsca/prefab:dood --repo repo.tld/org/project \
    --push --target name
```

#### Docker in Docker (DinD)

To get the *Prefab* Docker in Docker (DinD) image:

```
docker pull quay.io/lexsca/prefab:dind
```

To run the *Prefab* Docker in Docker image to build an push a build target:

```
docker run --rm -it -v $(/bin/pwd):/build -w /build --privileged \
    -e REGISTRY_AUTH=$(jq -c . ~/.docker/config.json | base64) \                
    quay.io/lexsca/prefab:dind --repo repo.tld/org/project \
    --push --target name
```


## Contributing

Bug reports are welcome.  Pull requests even more so.

Before making any changes, first ensure the development environment is functional and the extant linting and tests are passing.  To start a development environment, clone or fork this source repo and follow the instructions below.

Alternatively, it's fine to create a virtual environment an install packages from `requirements.txt` and `requirements-dev.txt` files. The Python version should be 3.7 or later.

#### Prerequisites

1. POSIX Shell (e.g. bash)
1. Docker
1. GNU Make

#### Create environment


To create a development runtime environment:

```
$ make bootstrap
```

The above will create a minimal environment that will allow *Prefab* to build its development environment image.  This image can be used to run linting and tests:

```
$ docker images quay.io/lexsca/prefab:dev
REPOSITORY              TAG                 IMAGE ID            CREATED              SIZE
quay.io/lexsca/prefab   dev                 ddee1cafb775        About a minute ago   429MB
```

#### Use environment


Once created, the development image can used via:

```
$ make shell 
docker run --rm -it -v /Users/lexsca/git/prefab:/prefab -w /prefab \
		-v /var/run/docker.sock:/docker.sock -e PYTHONPATH=/prefab/lib \
		--entrypoint /bin/bash quay.io/lexsca/prefab:dev --login -o vi
3053ae861610:/prefab# make test
```

This will mount the docker socket and current working directory in an environment where tests can be run, dependencies built, or a debugger invoked to aid in iterating.

The `make test` command should pass before attempting to submit any code changes.
