####################
Prefab build example
####################

This is an example of using *Prefab* to build a Python app with package
dependencies that can take several minutes to compile. Building this app
demonstrates how *Prefab* caching works and how it can make builds
faster.

.. note:: The command blocks below expect to be run in the `example <https://github.com/lexsca/prefab/tree/main/example>`__ directory of this source repo.

Build app
=========

To run *Prefab* as a container to build the example app in a Linux or
Mac terminal::

    docker run --rm -v `pwd`:/build -w /build \
        -v /var/run/docker.sock:/var/run/docker.sock \
        quay.io/lexsca/prefab:dood \
        --repo quay.io/lexsca/example --target app:app

To run *Prefab* locally as a Python package to build the example app::

    pip install container-prefab
    prefab --repo quay.io/lexsca/example --target app:app

Inspect build
=============

After building there should be two images::

    docker images quay.io/lexsca/example
    REPOSITORY               TAG                 IMAGE ID            CREATED             SIZE
    quay.io/lexsca/example   app                 4205b14b1d16        16 seconds ago      74MB
    quay.io/lexsca/example   090b6f96b40a        c9b5633ac7f8        26 seconds ago      4.39MB

Notice that the image with the hexadecimal tag is the ``packages``
target that was pulled instead of having to build it, and that the image
tag is a truncated version of the target digest::

    docker inspect quay.io/lexsca/example:090b6f96b40a \
        | jq -M '.[].Config.Labels'
    {
      "prefab.digest": "sha256:090b6f96b40aeeac66a0a87ef6ea3ca682f337b580851965b97f16cb5de00280",
      "prefab.target": "packages"
    }

*Prefab* computes a digest of the build target based on the target name,
the Dockerfile, and any ``watch_files`` in the
```prefab.yml`` <https://github.com/lexsca/prefab/blob/main/example/prefab.yml>`__
configuration file. This provides a *deterministic* identifer. So long
as none of the content changes, the digest and the tag of the image to
pull will be the same. This allows an image for a build target to be
pulled before attempting a potentially more time consuming build.

Build app without cache (optional)
==================================

To see how long it would take to build the app without a cached packages
image, append ``--force`` to the arguments to force building each
target. This takes approximately 7 minutes on a 2017 MacBook Pro with 2
CPUs and 2 GB of RAM allocated to Docker.

To run *Prefab* as a container to force build the example app in a Linux
or Mac terminal::

    docker run --rm -v `pwd`:/build -w /build \
        -v /var/run/docker.sock:/var/run/docker.sock \
        quay.io/lexsca/prefab:dood \
        --repo quay.io/lexsca/example --target app:app --force

To run *Prefab* locally as a Python package to force build the example
app::

    pip install container-prefab
    prefab --repo quay.io/lexsca/example --target app:app --force

Run and test app (optional)
===========================

The example app really is functional, albeit not terribly interesting.
It takes a POST with HTML content and returns a plain text rendering of
the HTML content. To run and test it::

    docker run -it --rm -p 8000:8000 quay.io/lexsca/example:app

    curl -d '<html>Prefab &#x26a1;</html>' http://127.0.0.1:8000/
