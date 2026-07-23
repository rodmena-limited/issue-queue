"""Web server entry point."""

from typing import Optional

from issuedb.web._app import app


def run_server(
    host: str = "127.0.0.1",
    port: int = 7760,
    debug: bool = False,
    db_path: Optional[str] = None,
) -> None:
    """Run the web server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Enable debug mode (uses Flask dev server).
        db_path: Path to the database file to serve (default: ./.issue.db).
    """
    app.config["ISSUEDB_DB_PATH"] = db_path

    if debug:
        print(f"Starting .issue.db Web UI on http://{host}:{port} (DEBUG mode with Flask)")
        app.run(host=host, port=port, debug=True)
    else:
        try:
            from waitress import serve  # type: ignore

            print(
                f"Starting .issue.db Web UI on http://{host}:{port} (Production mode with Waitress, 8 threads)"
            )
            serve(app, host=host, port=port, threads=8)
        except ImportError:
            print("Warning: 'waitress' not found. Falling back to Flask development server.")
            print("Install with: pip install issuedb[web]")
            print(
                f"Starting .issue.db Web UI on http://{host}:{port} (Development mode with Flask)"
            )
            app.run(host=host, port=port, debug=False)
