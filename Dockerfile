FROM python:3.11.4-slim

WORKDIR /app

COPY . .

CMD [ "python3", "./main.py" ]