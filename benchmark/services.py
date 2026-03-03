"""Minimal Flask microservices that simulate real processing with time.sleep().

Topology:  client -> api_server (port 5001) -> db_server (port 5002)

Each server has a configurable number of "workers" (Werkzeug threads)
and a configurable mean service time (exponential distribution).
"""
import argparse
import random
import time

from flask import Flask, jsonify


def create_api_app(mean_service_time: float = 0.15, db_url: str = "http://127.0.0.1:5002/query"):
    app = Flask("api_server")

    @app.route("/request")
    def handle_request():
        service_time = random.expovariate(1.0 / mean_service_time)
        time.sleep(service_time)

        import requests as req_lib
        start = time.monotonic()
        resp = req_lib.get(db_url, timeout=30)
        db_latency = time.monotonic() - start

        return jsonify({
            "api_service_time": service_time,
            "db_latency": db_latency,
            "db_status": resp.status_code,
        })

    return app


def create_db_app(mean_service_time: float = 0.4):
    app = Flask("db_server")

    @app.route("/query")
    def handle_query():
        service_time = random.expovariate(1.0 / mean_service_time)
        time.sleep(service_time)
        return jsonify({"status": "ok", "service_time": service_time})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["api", "db"])
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--mean-service-time", type=float, default=0.15)
    args = parser.parse_args()

    if args.role == "api":
        app = create_api_app(mean_service_time=args.mean_service_time)
    else:
        app = create_db_app(mean_service_time=args.mean_service_time)

    from werkzeug.serving import make_server
    server = make_server("127.0.0.1", args.port, app, threaded=True)
    print(f"[{args.role}] Listening on port {args.port} (workers={args.workers}, mean_st={args.mean_service_time})")
    server.serve_forever()
