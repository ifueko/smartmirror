I make no promises with this code. Use at your own risk :)

## Jailbreak instructions for lululemon studio mirror
https://github.com/olm3ca/mirror

## Installation + Usage
```
conda create -n smartmirror python=3.11
python -m pip install -r requirements.txt
conda install -c conda-forge 'ffmpeg<7' # not sure if this is actually necessary
python manage.py collectstatic
uvicorn smartmirror.asgi:application --host 127.0.0.1 --port 8000
```

I likely forgot things, but will update this readme to be more helpful eventually.
