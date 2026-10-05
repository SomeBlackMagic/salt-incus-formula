.DEFAULT_GOAL := help

## Lint
lint: ## Run all pre-commit hooks on all files
	pre-commit run --all-files --color always --verbose

lint-commitlint: ## Run commitlint-ci (manual stage)
	pre-commit run --color always --hook-stage manual --verbose commitlint-ci

lint-yaml: ## Run yamllint only
	pre-commit run --all-files --color always --verbose yamllint

lint-salt: ## Run salt-lint only
	pre-commit run --all-files --color always --verbose salt-lint

lint-shellcheck: ## Run shellcheck only
	pre-commit run --all-files --color always --verbose shellcheck

## Pre-commit setup
setup-pre-commit: ## Install pre-commit hook environments
	pre-commit install-hooks

install-hooks: ## Install pre-commit git hooks
	pre-commit install

## Test (Kitchen)
setup-kitchen: ## Install Kitchen Ruby dependencies
	bundle install

kitchen-create: ## Create Kitchen instances
	bundle exec kitchen create

kitchen-converge: ## Converge Kitchen instances
	bundle exec kitchen converge

kitchen-verify: ## Run Kitchen tests (create + converge + verify)
	bundle exec kitchen verify

kitchen-destroy: ## Destroy Kitchen instances
	bundle exec kitchen destroy

kitchen-test: ## Full Kitchen test cycle (create, converge, verify, destroy)
	bundle exec kitchen test

## Helpers
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: lint lint-commitlint lint-yaml lint-salt lint-shellcheck \
        setup-pre-commit install-hooks \
        setup-kitchen kitchen-create kitchen-converge kitchen-verify kitchen-destroy kitchen-test \
        help
