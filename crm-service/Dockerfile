FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# По умолчанию запускается API. Воркер запускается той же образом,
# но с командой:  arq app.queue.worker.WorkerSettings
CMD ["python", "-m", "app.main"]
