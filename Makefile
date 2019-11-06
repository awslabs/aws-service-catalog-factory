help:
	@echo "Usage:"
	@echo "    make help        show this message"
	@echo "    make setup       create virtual environment and install dependencies"
	@echo "    make activate    enter virtual environment"
	@echo "    make test        run the test suite"
	@echo "    exit             leave virtual environment"

setup:
	pip install pipenv
	pipenv sync --dev --three

activate:
	pipenv shell -c

test:
	pipenv run pip install .
	pipenv check
	pipenv run -- py.test --cov=./servicecatalog_factory --cov-branch

prepare-deploy:
	pipenv run pipenv-setup sync
	pipenv run python setup.py sdist

.PHONY: help activate test setup prepare-deploy
