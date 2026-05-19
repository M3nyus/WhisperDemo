FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# pip + setuptools rendbetétele
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3000

#CMD ["sleep", "3600"]
CMD ["python3", "server.py"]