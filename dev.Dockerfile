# Stage 1: Build
FROM python:3-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG USERNAME=appuser
ENV APP_PATH=/app

# Create unprivileged user
RUN adduser $USERNAME -s /sbin/nologin -D

# Set working directory
WORKDIR $APP_PATH

# Update dependencies & install requirements
RUN apk update
RUN apk upgrade
# RUN apk add --no-cache cargo rust gcc python3-dev musl-dev linux-headers make g++
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m pip install --upgrade pip setuptools wheel
COPY --chown=$USERNAME:$USERNAME ./requirements.txt ./requirements.txt
RUN python -m pip install -r $APP_PATH/requirements.txt

COPY --chown=$USERNAME:$USERNAME ./src .

# Set entrypoint
ENTRYPOINT ["fastapi", "run", "main.py"]