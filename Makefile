.PHONY: install-requirements refesh-requirements format lint test

requirements.txt: requirements.in
	pip-compile -v requirements.in

requirements-dev.txt: requirements-dev.in
	pip-compile -v requirements-dev.in

install-requirements: requirements.txt requirements-dev.txt
	pip install -U -r requirements.txt
	pip install -U -r requirements-dev.txt

refesh-requirements:
	rm -f requirements.txt requirements-dev.txt
	$(MAKE) requirements.txt
	$(MAKE) requirements-dev.txt

format:
	black .

lint:
	flake8 .
	bandit .

test: format lint
