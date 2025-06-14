## Install Requirements
```
conda create -n smartmirror python=3.11
conda activate smartmirror
python -m pip install -r requirements.txt
```
## Download pinterest images to vision board
for this command, board must be public, see [gallery-dl docs](https://github.com/mikf/gallery-dl/) for login instructions on private boards

alternatively, create a folder of images called "vision" and place it in mirror/static/mirror/
```
python -m pip install gallery-dl
gallery-dl -d mirror/static/mirror/vision -o directory="" [PINTEREST_BOARD_URL]
```
## Create and update env
```
cp example.env .env
vi .env # or whatever editor you use
```

## Run Server
Note: First run will take a while because whisper needs to download weights the first time.
```
python manage.py collectstatic --noinput
uvicorn smartmirror.asgi:application --host 127.0.0.1 --port 8000
```
Now the mirror UI will show up at localhost:8000 or 127.0.0.1:8000

## Jailbreak instructions for lululemon studio mirror
https://github.com/olm3ca/mirror
