.PHONY: setup run stop logs clean ts-setup ts-build ts-dev

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
	@echo "\n✅ All services running. Use 'make stop' to shut down."

stop:
	@pkill -f "python server.py" 2>/dev/null || true
	@pkill -f "python timeline_server.py" 2>/dev/null || true
	@pkill -f "python listener.py" 2>/dev/null || true
	@pkill -f "python mcp_dispatcher.py" 2>/dev/null || true
	@echo "✅ All services stopped."

logs:
	@tail -f /tmp/xmcp-*.log 2>/dev/null || echo "No log files found."

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
