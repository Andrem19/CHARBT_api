# Dockerfile для Flask приложения
FROM python:3.8
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["sh", "-c", "sleep 5; gunicorn --worker-class gthread --workers 4 --log-level debug --access-logfile - -b :5000 main:app"]

