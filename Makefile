.PHONY: install check test dashboard all clean

install:            ## Install the toolkit in editable mode with dev deps
	python -m pip install -e ".[dev]"

check:              ## Run every stewardship compliance check
	ds-steward check

test:               ## Run the pytest suite
	pytest -v

dashboard:          ## Regenerate docs/dashboard.html from current repo state
	ds-steward dashboard --output docs/dashboard.html

all: check test dashboard

clean:              ## Remove caches and build artifacts
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
