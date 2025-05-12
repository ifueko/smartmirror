## Jailbreak instructions for lululemon studio mirror
https://github.com/olm3ca/mirror

## Installation
python -m pip install -r requirements.txt
python manage.py collectstatic
uvicorn smartmirror.asgi:application --host 127.0.0.1 --port 8000
