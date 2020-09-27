.PHONY: clean build install-requirements refesh-requirements format lint \
		test version publish push-image upload-pypi push-release-tag

IMAGE_REPO ?= quay.io/lexsca/prefab
VERSION ?= $(shell TZ=UTC git log -1 --format='%cd' \
	--date='format-local:%y.%m.%d%H%M%S' HEAD)
VERSION_PY ?= lib/prefab/version.py
RELEASE_TAG ?= $(VERSION)

help: MAKEFILE = $(lastword $(MAKEFILE_LIST))
help:
	@$(MAKE) -pRrq -f $(MAKEFILE) : 2>/dev/null | \
	awk '$$0 !~ /^\t/ && $$1 ~ /^[a-zA-Z0-9].*:$$/ {print $$1}' | \
	cut -d: -f1 | egrep -v '^$(MAKEFILE)$$|^$@$$' | sort -n

clean:
	rm -fr lib/*.egg-info dist build .pytest_cache $(VERSION_PY)
	find . -type d -name __pycache__ -exec /bin/rm -fr {} +
	find . -depth -type f -name '*.pyc' -exec /bin/rm -fr {} +
	$(MAKE) -C doc clean

version:
	echo '__version__ = "$(VERSION)"' > $(VERSION_PY)

build: version
	python setup.py sdist bdist_wheel
	docker build --squash -t $(IMAGE_REPO):$(VERSION) .
	docker image prune -f

push-image:
	docker tag $(IMAGE_REPO):$(VERSION) $(IMAGE_REPO):latest
	docker push $(IMAGE_REPO):$(VERSION)
	docker push $(IMAGE_REPO):latest

upload-pypi:
	twine upload dist/*

push-release-tag:
	git tag $(RELEASE_TAG) HEAD
	git push origin $(RELEASE_TAG)

publish: build upload-pypi push-image push-release-tag

requirements.txt: requirements.in
	pip-compile -v requirements.in

requirements-dev.txt: requirements-dev.in
	pip-compile -v requirements-dev.in

install-requirements: requirements.txt requirements-dev.txt
	pip install -U pip
	pip install -U -r requirements.txt
	pip install -U -r requirements-dev.txt

refesh-requirements:
	rm -f requirements.txt requirements-dev.txt
	$(MAKE) requirements.txt
	$(MAKE) requirements-dev.txt

format:
	black .

lint: version
	black --check --diff .
	flake8 .
	bandit -r bin lib
	mypy --ignore-missing-imports --cache-dir=/dev/null .

test: lint
	pytest --random-order --cov=lib --cov-report=term-missing tests
