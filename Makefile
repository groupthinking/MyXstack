.PHONY: setup run stop logs test clean ts-setup ts-build ts-dev ci ci-python ci-python-lint ci-python-test ci-node ci-node-install ci-node-build

# ─── Python Stack ───────────────────────────

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	@test -f .env || cp env.example .env
	@echo "\n✅ Setup complete. Edit .env with your API keys, then run: make run"

run:
	@echo "Starting all services..."
	. .venv/bin/activate && python server.py &
	. .venv/bin/activate && python timeline_server.py &
	@sleep 2
	. .venv/bin/activate && python listener.py &
	. .venv/bin/activate && python mcp_dispatcher.py &
	@echo "\n✅ All services running. Approval UI: http://localhost:8080/ui"
	@echo "   Use 'make stop' to shut down."

stop:
	@pkill -f "python server.py" 2>/dev/null || true
	@pkill -f "python timeline_server.py" 2>/dev/null || true
	@pkill -f "python listener.py" 2>/dev/null || true
	@pkill -f "python mcp_dispatcher.py" 2>/dev/null || true
	@echo "✅ All services stopped."

logs:
	@tail -f /tmp/xmcp-*.log 2>/dev/null || echo "No log files found."

test:
	@test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -q -r requirements-dev.txt && pytest tests/ -v

# ─── CI parity ──────────────────────────────
# Every gate in .circleci/config.yml, runnable locally. If it can't be
# reproduced here in one command, it doesn't belong in the pipeline.
# Order matches the workflow: install → lint → build → test.

ci: ci-python ci-node
	@echo "\n✅ All CI gates passed — safe to push."

ci-python:
	@test -d .venv || python3 -m venv .venv
	# Mirrors CircleCI install_python_deps (fresh venv = fresh container)
	. .venv/bin/activate && pip install -q --upgrade pip && pip install -q -r requirements-dev.txt
	$(MAKE) ci-python-lint
	$(MAKE) ci-python-test

ci-python-lint:
	# Mirrors python_lint: `python -m flake8 .`
	@if [ -d .venv ]; then . .venv/bin/activate; fi && python -m flake8 .

ci-python-test:
	# Mirrors python_test: `python -m pytest -q`
	@if [ -d .venv ]; then . .venv/bin/activate; fi && python -m pytest -q $(PYTEST_ARGS)

ci-node: ci-node-install
	# Mirrors node_build: `npm run build` (tsc) — only gate that executes code
	$(MAKE) ci-node-build
	# node_lint / node_test are no-ops: package.json has no lint/test scripts,
	# so CircleCI skips them and so do we.

ci-node-install:
	# Mirrors node_install: `npm ci` when a lockfile exists
	npm ci

ci-node-build:
	# Mirrors node_build: `tsc`
	npm run build

# ─── Docker ─────────────────────────────────

up:
	docker compose up -d --build
	@echo "\n✅ All services running in Docker."

down:
	docker compose down

# ─── TypeScript Stack ───────────────────────

ts-setup:
	npm install

ts-build:
	npm run build

ts-dev:
	npm run dev

# ─── Cleanup ────────────────────────────────

clean:
	rm -rf .venv dist node_modules __pycache__
