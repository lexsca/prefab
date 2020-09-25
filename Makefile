.PHONY: clean build publish install-requirements refesh-requirements format lint test

clean:
	rm -fr lib/*.egg-info dist build .pytest_cache
	find . -type d -name __pycache__ -exec /bin/rm -fr {} +
	find . -depth -type f -name '*.pyc' -exec /bin/rm -fr {} +

build: clean
	python setup.py sdist bdist_wheel
	docker build --squash -t quay.io/lexsca/prefab .
	docker image prune -f

publish:
	twine upload dist/*

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

lint:
	black --check --diff .
	flake8 .
	bandit -r bin lib
	mypy --ignore-missing-imports --cache-dir=/dev/null .

test: lint
	pytest --random-order --cov=lib --cov-report=term-missing tests
