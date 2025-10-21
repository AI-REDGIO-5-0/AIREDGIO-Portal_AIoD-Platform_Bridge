# Stage 1: Build
FROM python:3-alpine AS builder

ENV APP_PATH=/app

# Set working directory
WORKDIR $APP_PATH

# Update dependencies & install requirements
RUN apk update
RUN apk upgrade
# RUN apk add --no-cache cargo rust gcc python3-dev musl-dev linux-headers make g++
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m pip install --upgrade pip setuptools wheel
COPY ./requirements.txt ./requirements.txt
RUN python -m pip install -r $APP_PATH/requirements.txt

# Stage 2: Final image
FROM python:3-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG USERNAME=appuser
ENV APP_PATH=/app

RUN adduser $USERNAME -s /sbin/nologin -D
# Set working directory
WORKDIR $APP_PATH

# Copy the application from the builder stage
COPY --chown=$USERNAME:$USERNAME --from=builder /opt/venv /opt/venv
COPY --chown=$USERNAME:$USERNAME ./src .

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

# Set entrypoint
ENTRYPOINT ["fastapi", "run", "main.py"]