# !/bin/sh

uvicorn demo.asgi:application --host 0.0.0.0 --port 8000 --reload
