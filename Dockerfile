FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app
COPY db/ ./db

RUN mkdir -p /app/uploads

EXPOSE 8501 8000

CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
