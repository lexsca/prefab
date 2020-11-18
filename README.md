# Prefab

#### *Build container images faster* ⚡️

[![https://xkcd.com/303/](https://imgs.xkcd.com/comics/compiling.png)](https://xkcd.com/license.html)

[![shields.io](https://img.shields.io/pypi/pyversions/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![shields.io](https://img.shields.io/pypi/v/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![shields.io](https://img.shields.io/pypi/wheel/container-prefab.svg)](https://pypi.org/project/container-prefab/) [![readthedocs.org](https://readthedocs.org/projects/prefab/badge/?version=stable)](https://prefab.readthedocs.io/en/stable/?badge=stable) [![coveralls.io](https://coveralls.io/repos/github/lexsca/prefab/badge.svg?branch=main)](https://coveralls.io/github/lexsca/prefab?branch=main) [![shields.io](https://img.shields.io/github/license/lexsca/prefab.svg)](https://github.com/lexsca/prefab/blob/master/LICENSE) [![shields.io](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


A variation of the above [xkcd webcomic](https://xkcd.com/303/) is,  "containers are building!"  If it takes way to long to build your containers, *Prefab* might be able to help!

*Prefab* is a Python-based container build tool that uses deterministic remote caching to help reduce build times, especially in cases of compiled or other CPU intensive builds.  Unlike [BuildKit](https://github.com/moby/buildkit#cache) and the [Docker CLI](https://docs.docker.com/engine/reference/commandline/build/#specifying-external-cache-sources), which use container layer caching, *Prefab* caches based on the ***content*** that goes into a container image.