FROM python:3.11-bullseye
RUN pip install  --no-cache-dir poetry==1.4.0

COPY poetry.lock pyproject.toml /app/
WORKDIR /app
RUN poetry install --only main

COPY . .
CMD ["poetry", "run", "python3", "main.py"]
