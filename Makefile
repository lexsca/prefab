.PHONY: bootstrap build cache-clean clean docker-clean format \
		git-tag-push lint refesh-requirements shell spotless test version

IMAGE_REPO ?= lexsca/prefab
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
		.coverage coverage.xml *.spec docs/_build/* docs/_build/.??* \
		.mypy_cache
	find . -type d -name __pycache__ -exec /bin/rm -fr {} +
	find . -depth -type f -name '*.pyc' -exec /bin/rm -fr {} +

docker-clean:
	docker system prune -af
	docker volume prune -f

spotless: clean docker-clean

bootstrap:
	docker build -t $(IMAGE_REPO):bootstrap -f image/Dockerfile.tools .
	docker run --rm -it -v $(shell /bin/pwd):/build -w /build \
		-v /var/run/docker.sock:/var/run/docker.sock \
		--entrypoint /bootstrap.sh $(IMAGE_REPO):bootstrap \
		-c image/prefab.yaml -r $(IMAGE_REPO) -t dev:dev

shell:
	docker run --rm -it -v $(shell /bin/pwd):/prefab -w /prefab \
		-v /var/run/docker.sock:/docker.sock -e PYTHONPATH=/prefab/lib \
		--entrypoint /bin/bash $(IMAGE_REPO):dev --login -o vi

format:
	black .

lint: clean
	black --check --diff .
	flake8 .
	bandit -r bin lib
	mypy --ignore-missing-imports .

test: clean
	pytest -v --random-order --cov=lib --cov-report=term-missing tests

version:
	echo '__version__ = "$(VERSION)"' > $(VERSION_PY)

smoke-test:
	# build prefab from prefab dind and dood artifacts
	$(MAKE) cache-clean
	docker run --rm -it -v $(shell /bin/pwd):/build -w /build \
		-v /var/run/docker.sock:/docker.sock $(IMAGE_REPO):dood-$(VERSION) \
		-c image/prefab.yaml -r $(IMAGE_REPO) -t dind dood
	docker run --rm -it -v $(shell /bin/pwd):/build -w /build --privileged \
		$(IMAGE_REPO):dind-$(VERSION) -c image/prefab.yaml \
		-r $(IMAGE_REPO) -t dind dood

cache-clean: IMAGES = $(shell \
	docker images --format '{{.Repository}}:{{.Tag}}' ${IMAGE_REPO} | \
	awk -F: '$$2 ~ /^[0-9a-f]{12}$$/')
cache-clean:
	$(foreach image,$(IMAGES),docker rmi $(image);)
	docker image prune -f

git-tag-push:
	git tag v$(RELEASE_TAG) HEAD
	git push origin v$(RELEASE_TAG)

requirements.txt: requirements.in
	pip-compile -v requirements.in

requirements-dev.txt: requirements-dev.in
	pip-compile -v requirements-dev.in

refresh-requirements:
	rm -f requirements.txt requirements-dev.txt
	$(MAKE) requirements.txt requirements-dev.txt

none-artifact:
	# used by tests/test_image_docker.py:test_pull_prefab_none
	echo 'FROM scratch' | docker build --label prefab.target=none -t $(IMAGE_REPO):none -
	docker push $(IMAGE_REPO):none
