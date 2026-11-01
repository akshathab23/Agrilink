#!/usr/bin/env bash
set -e

# Change directory to the repository root
cd "$(dirname "$0")"

echo "==> AgriLink Startup Starting..."
echo "==> Working Directory: $(pwd)"

# 1. Trap signals for graceful process shutdown
cleanup() {
    echo "==> Shutting down AgriLink services..."
    if [ -n "$GUNICORN_PID" ]; then
        echo "==> Stopping Flask backend (PID: $GUNICORN_PID)..."
        kill -TERM "$GUNICORN_PID" 2>/dev/null || true
        wait "$GUNICORN_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGTERM SIGINT

# 2. Run database migration safely (creates tables if missing, non-destructive)
echo "==> Running database migrations..."
if ! python backend/scripts/migrate_auth_phase3.py; then
    echo "ERROR: Database migration failed! Aborting startup to protect data integrity."
    exit 1
fi
echo "==> Database migration verified successfully."

# 3. Initialize market-price dataset only if the table is empty
echo "==> Verifying market-price dataset..."
if ! python backend/scripts/load_data.py; then
    echo "ERROR: Market-price dataset initialization failed! Aborting startup."
    exit 1
fi

# 4. Start Flask API with Gunicorn in background on 127.0.0.1:5000
echo "==> Starting Flask backend on 127.0.0.1:5000..."
export PYTHONPATH=".:$PYTHONPATH"
gunicorn --bind 127.0.0.1:5000 --workers 2 --threads 4 --timeout 120 backend.app:app &
GUNICORN_PID=$!

# Wait for Flask API to become ready before launching Streamlit
echo "==> Waiting for backend health check..."
BACKEND_READY=0
for i in {1..30}; do
    if ! kill -0 "$GUNICORN_PID" 2>/dev/null; then
        echo "ERROR: Flask backend process died unexpectedly during startup."
        exit 1
    fi
    if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health')" >/dev/null 2>&1; then
        echo "==> Flask backend is ready on 127.0.0.1:5000."
        BACKEND_READY=1
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
    echo "ERROR: Flask backend health check timed out after 30 seconds."
    cleanup
    exit 1
fi

# 5. Start Streamlit in foreground on 0.0.0.0 using Render's $PORT
PORT="${PORT:-8501}"
echo "==> Starting Streamlit frontend on 0.0.0.0:$PORT..."
streamlit run frontend/app.py \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false

# Trigger cleanup once Streamlit exits
cleanup
