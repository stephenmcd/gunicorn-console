
gunicorn-console
----------------

A curses application for managing gunicorn processes. The ``ps`` command is polled for gunicorn processes named with the ``setproctitle`` package. A list of gunicorn process is shown with number of workers and keys for modifying the number of worker process per gunicorn as well as reloading the master gunicorn process.
