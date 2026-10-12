"""Run Sofia Media with Waitress on the loopback interface."""
import argparse
import logging
import os
import socket


def main(application=None):
    if application is None:
        from app import app
        application = app
    parser = argparse.ArgumentParser(description="Sofia Media local server")
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "15001")))
    parser.add_argument("--check", action="store_true", help="validate setup without starting a server")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    host = "127.0.0.1"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.check:
        print(f"Configuration OK: http://{host}:{args.port}")
        return
    try:
        with socket.socket() as probe:
            probe.bind((host, args.port))
    except OSError:
        parser.error(f"{host}:{args.port} is occupied; choose --port <free-port>")
    from waitress import serve
    print(f"Sofia Media: http://{host}:{args.port}", flush=True)
    serve(application, host=host, port=args.port, threads=8)


if __name__ == "__main__":
    main()
