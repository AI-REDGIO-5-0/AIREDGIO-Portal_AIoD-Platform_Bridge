FROM python:3.10-alpine

ARG USERNAME=appuser
ARG DIR=/home/$USERNAME
ENV VENV_NAME=venv

# Create unprivileged user
RUN adduser $USERNAME -s /sbin/nologin -D -h $DIR

USER $USERNAME
WORKDIR $DIR

# Create a python virtual environment and add it to PATH to use it without activating it
RUN python -m venv $VENV_NAME
ENV PATH="$DIR/$VENV_NAME/bin:$PATH"
# Install dependencies from requirements.txt
COPY --chown=$USERNAME:$USERNAME requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade --no-cache-dir pip setuptools wheel
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=$USERNAME:$USERNAME src/ ./

# Copy the crontab using the root user
USER root
COPY cron.tab /etc/crontab/$USERNAME

# Run the the cron daemon as the root user
CMD ["crond", "-f", "-c", "/etc/crontab"]