#!/bin/bash
# Run on PythonAnywhere Bash console from your backend folder
set -e

pip install -r requirements.txt
python manage.py migrate
echo "Done. Now reload the web app from the Web tab."
