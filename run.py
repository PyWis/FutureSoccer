import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))

    # Start the game scheduler once. Under the Werkzeug reloader only the
    # child (serving) process — identified by WERKZEUG_RUN_MAIN — starts it,
    # so events aren't processed twice.
    if os.environ.get('SCHEDULER_ENABLED', '1') == '1':
        if not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            from app.scheduler import start_scheduler
            start_scheduler(app)

    app.run(debug=debug, host=host, port=port)
