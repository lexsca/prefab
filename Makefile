.PHONY: clean build install-requirements refesh-requirements format lint \
		test version publish push-image upload-pypi push-release-tag

IMAGE_REPO ?= quay.io/lexsca/prefab
VERSION ?= $(shell TZ=UTC git log -1 --format='%cd' \
	--date='format-local:%y.%-m.%-d%H%M' HEAD)
VERSION_PY ?= lib/prefab/version.py
RELEASE_TAG ?= $(VERSION)

help: MAKEFILE = $(lastword $(MAKEFILE_LIST))
help:
	@$(MAKE) -pRrq -f $(MAKEFILE) : 2>/dev/null | \
	awk '$$0 !~ /^\t/ && $$1 ~ /^[a-zA-Z0-9].*:$$/ {print $$1}' | \
	cut -d: -f1 | egrep -v '^$(MAKEFILE)$$|^$@$$' | sort -n

clean:
	rm -fr lib/*.egg-info dist build .pytest_cache $(VERSION_PY) \
		image/*.whl image/requirements.txt
	find . -type d -name __pycache__ -exec /bin/rm -fr {} +
	find . -depth -type f -name '*.pyc' -exec /bin/rm -fr {} +
	$(MAKE) -C docs clean

docker-clean:
	docker system prune -af
	docker volume prune -f

version:
	echo '__version__ = "$(VERSION)"' > $(VERSION_PY)

build: clean version
	python setup.py sdist bdist_wheel
	cp dist/container_prefab-$(VERSION)-py3-none-any.whl image
	ln -fs container_prefab-$(VERSION)-py3-none-any.whl image/current-wheel
	cp requirements.txt image
	cd image && PYTHONPATH=../lib ../bin/container-prefab -r $(IMAGE_REPO) \
		-t app:$(VERSION)
	docker tag $(IMAGE_REPO):$(VERSION) $(IMAGE_REPO):latest

push-image:
	cd image && PYTHONPATH=../lib ../bin/container-prefab -r $(IMAGE_REPO) \
		-t app:$(VERSION) -p
	docker push $(IMAGE_REPO):latest

upload-pypi:
	twine upload dist/*

push-release-tag:
	git tag $(RELEASE_TAG) HEAD
	git push origin $(RELEASE_TAG)

publish: test build upload-pypi push-image push-release-tag

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
	$(MAKE) install-requirements

format:
	black .

lint:
	black --check --diff .
	flake8 bin lib tests
	bandit -r bin lib
	mypy --ignore-missing-imports --cache-dir=/dev/null .

test: clean lint
	pytest --random-order --cov=lib --cov-report=term-missing tests
