# gunicorn.conf.py

bind = "127.0.0.1:7777"   # Bind to IP address and port
workers = 2               # Number of worker processes
timeout = 120             # Timeout for workers
loglevel = "info"         # Logging level
accesslog = "/home/art/logs/gunicorn/gunicorn-access.log"  # Access log path
errorlog = "/home/art/logs/gunicorn/gunicorn-error.log"  # Error log path
