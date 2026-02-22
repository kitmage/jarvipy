#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/jarvis-pi"
SERVICE_NAME="jarvis.service"
LOGROTATE_NAME="jarvis.logrotate"
VENV_DIR="${APP_DIR}/.venv"
ENV_FILE="${APP_DIR}/.env"
LOG_FILE="/var/log/jarvis.log"

if [[ "${EUID}" -ne 0 ]]; then
  echo "install.sh must be run as root" >&2
  exit 1
fi

apt-get update
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  ffmpeg \
  portaudio19-dev \
  libatlas-base-dev

if ! getent group jarvis >/dev/null; then
  groupadd --system jarvis
fi

if ! id -u jarvis >/dev/null 2>&1; then
  useradd --system --gid jarvis --home-dir "${APP_DIR}" --shell /usr/sbin/nologin jarvis
fi

mkdir -p "${APP_DIR}"
cp -a . "${APP_DIR}/"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${APP_DIR}/.env.example" "${ENV_FILE}"
fi

touch "${LOG_FILE}"
chown jarvis:jarvis "${LOG_FILE}"
chmod 0640 "${LOG_FILE}"

install -m 0644 "${APP_DIR}/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
install -m 0644 "${APP_DIR}/${LOGROTATE_NAME}" "/etc/logrotate.d/jarvis"

chown -R jarvis:jarvis "${APP_DIR}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "Jarvis installation completed."
