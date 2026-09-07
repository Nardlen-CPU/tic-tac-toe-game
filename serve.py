"""Production entry point for Railway and local deployment checks."""
import os

from waitress import serve

from app import app


def main():
    # One process keeps the in-memory multiplayer rooms shared by all threads.
    # Railway terminates HTTPS before forwarding requests to this HTTP listener.
    serve(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', '5000')),
        threads=8,
        url_scheme='https' if os.environ.get('RAILWAY_ENVIRONMENT_ID') else 'http',
    )


if __name__ == '__main__':
    main()
