.PHONY: bootstrap build cache-clean cache-push clean docker-clean format \
		git-tag-push image-push lint publish push-image push-release-tag \
		pypi-upload refesh-requirements release shell spotless test \
		upload-pypi version

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
		.coverage coverage.xml *.spec docs/_build/* docs/_build/.??*
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

lint:
	black --check --diff .
	flake8 .
	bandit .
	mypy --ignore-missing-imports --cache-dir=/dev/null .

test: clean lint
	pytest -v --random-order --cov=lib --cov-report=term-missing tests

version:
	echo '__version__ = "$(VERSION)"' > $(VERSION_PY)

build:
	bin/prefab -c image/prefab.yaml -r $(IMAGE_REPO) \
		-t pypi:pypi-$(VERSION)  dind:dind-$(VERSION) dood:dood-$(VERSION)

release: version
	docker run --rm -it -v $(shell /bin/pwd):/prefab -w /prefab \
		-v /var/run/docker.sock:/docker.sock -e PYTHONPATH=lib \
		$(IMAGE_REPO):dev make test version build

smoke-test:
	# build prefab from prefab dind and dood artifacts
	$(MAKE) cache-clean
	docker run --rm -it -v $(shell /bin/pwd):/build -w /build \
		-v /var/run/docker.sock:/docker.sock $(IMAGE_REPO):dood-$(VERSION) \
		-c image/prefab.yaml -r $(IMAGE_REPO) -t dind dood pypi
	docker run --rm -it -v $(shell /bin/pwd):/build -w /build --privileged \
		$(IMAGE_REPO):dind-$(VERSION) -c image/prefab.yaml \
		-r $(IMAGE_REPO) -t dind dood pypi

cache-clean: IMAGES = $(shell \
	docker images --format '{{.Repository}}:{{.Tag}}' ${IMAGE_REPO} | \
	awk -F: '$$2 ~ /^[0-9a-f]{12}$$/')
cache-clean:
	$(foreach image,$(IMAGES),docker rmi $(image);)
	docker image prune -f

cache-push:
	@docker run --rm -it -v $(shell /bin/pwd):/build -w /build \
		-v /var/run/docker.sock:/docker.sock -e PYTHONPATH=lib \
		-e REGISTRY_AUTH=$(shell jq -c . ~/.docker/config.json | base64) \
		$(IMAGE_REPO):dev bin/prefab -c image/prefab.yaml \
		-r $(IMAGE_REPO) -t dist -p tools wheels dev-wheels dist

image-push:
	docker tag $(IMAGE_REPO):dind-$(VERSION) $(IMAGE_REPO):dind
	docker tag $(IMAGE_REPO):dood-$(VERSION) $(IMAGE_REPO):dood
	docker push $(IMAGE_REPO):dind-$(VERSION)
	docker push $(IMAGE_REPO):dood-$(VERSION)
	docker push $(IMAGE_REPO):dind
	docker push $(IMAGE_REPO):dood

pypi-upload:
	@docker run --rm -it -e TWINE_PASSWORD=$(TWINE_PASSWORD) \
		$(IMAGE_REPO):pypi-$(VERSION)

git-tag-push:
	git tag v$(RELEASE_TAG) HEAD
	git push origin v$(RELEASE_TAG)

publish: image-push pypi-upload git-tag-push

deploy: spotless bootstrap release smoke-test publish

requirements.txt: requirements.in
	pip-compile -v requirements.in

requirements-dev.txt: requirements-dev.in
	pip-compile -v requirements-dev.in

refresh-requirements:
	rm -f requirements.txt requirements-dev.txt
	$(MAKE) requirements.txt requirements-dev.txt
