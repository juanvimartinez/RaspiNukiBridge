FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    dbus \
    bluez \
    bluetooth \
    libglib2.0-0 \
    libglib2.0-dev \
    build-essential \
    libffi-dev \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone https://github.com/juanvimartinez/RaspiNukiBridge.git . \
    && pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
