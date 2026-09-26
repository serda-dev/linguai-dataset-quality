.PHONY: test
test:
	@set -eu; test_project=linguai_quality_test_$$$$; trap 'docker compose -p "$$test_project" -f compose.test.yaml down -v --remove-orphans' EXIT; docker compose -p "$$test_project" -f compose.test.yaml build; docker compose -p "$$test_project" -f compose.test.yaml run --rm tests
