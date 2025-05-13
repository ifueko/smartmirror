## Jailbreak instructions for lululemon studio mirror
https://github.com/olm3ca/mirror

## Installation
conda create -n smartmirror python=3.11
python -m pip install -r requirements.txt
conda install -c conda-forge 'ffmpeg<7'

python manage.py collectstatic
uvicorn smartmirror.asgi:application --host 127.0.0.1 --port 8000
