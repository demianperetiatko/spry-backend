FROM python:3.10

WORKDIR ./code

COPY requirements.txt ./code/requirements.txt
RUN pip install --no-cache-dir -r ./code/requirements.txt

COPY ./service_views /code/service_views
COPY ./models /code/models
COPY ./migrations /code/migrations
COPY ./utils /code/utils

COPY main.py /code/main.py

CMD [ "uvicorn", "main:app", "--reload", "--host", "0.0.0.0" ]