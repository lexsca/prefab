######
Prefab
######

Build container images faster ⚡️

.. image:: https://img.shields.io/pypi/pyversions/container-prefab.svg
    :target: https://pypi.org/project/container-prefab/

.. image:: https://img.shields.io/pypi/v/container-prefab.svg
    :target: https://pypi.org/project/container-prefab/

.. image:: https://img.shields.io/pypi/wheel/container-prefab.svg
    :target: https://pypi.org/project/container-prefab/

.. image:: https://readthedocs.org/projects/prefab/badge/?version=stable
    :target: https://prefab.readthedocs.io/en/stable/?badge=stable

.. image:: https://codecov.io/gh/lexsca/prefab/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/lexsca/prefab

.. image:: https://img.shields.io/github/license/lexsca/prefab.svg
    :target: https://github.com/lexsca/prefab/blob/master/LICENSE

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

*Prefab* is a build tool that helps reduce the time it takes to create
container images.  It accomplishes this via deterministic builds and remote caching.
If a container image build takes several minutes to complete, building the same 
artifacts each time, *Prefab* might be able to help!
