#!/usr/bin/env bash
set -euo pipefail

APP_NAME="jarvis"
APP_USER="jarvis"
APP_GROUP="jarvis"
INSTALL_DIR="${INSTALL_DIR:-/opt/jarvis-pi}"
SERVICE_NAME="jarvis.service"
LOGROTATE_NAME="jarvis"
LOG_FILE="/var/log/jarvis.log"
ENV_FILE="${INSTALL_DIR}/.env"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "This installer must run as root (sudo)." >&2
    exit 1
  fi
}

install_os_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found; skipping OS package installation." >&2
    return
  fi

  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    libatlas-base-dev \
    libportaudio2 \
    ffmpeg \
    logrotate \
    sysstat
}

ensure_system_account() {
  if ! getent group "${APP_GROUP}" >/dev/null; then
    groupadd --system "${APP_GROUP}"
  fi

  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --gid "${APP_GROUP}" --home-dir "${INSTALL_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
  fi
}

install_application_files() {
  mkdir -p "${INSTALL_DIR}"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.git/' \
      --exclude '.venv/' \
      --exclude '__pycache__/' \
      --exclude '.pytest_cache/' \
      "${SCRIPT_DIR}/" "${INSTALL_DIR}/"
  else
    cp -a "${SCRIPT_DIR}/." "${INSTALL_DIR}/"
    rm -rf "${INSTALL_DIR}/.git" "${INSTALL_DIR}/.venv" "${INSTALL_DIR}/__pycache__" "${INSTALL_DIR}/.pytest_cache"
  fi

  chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
}

setup_python_env() {
  python3 -m venv "${INSTALL_DIR}/.venv"
  "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
  "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
}

setup_logs() {
  mkdir -p "$(dirname "${LOG_FILE}")"
  touch "${LOG_FILE}"
  chown "${APP_USER}:${APP_GROUP}" "${LOG_FILE}"
  chmod 0640 "${LOG_FILE}"
}

install_service() {
  local service_target="/etc/systemd/system/${SERVICE_NAME}"
  local logrotate_target="/etc/logrotate.d/${LOGROTATE_NAME}"

  install -m 0644 "${INSTALL_DIR}/jarvis.service" "${service_target}"
  sed -i "s#^WorkingDirectory=.*#WorkingDirectory=${INSTALL_DIR}#" "${service_target}"
  sed -i "s#^EnvironmentFile=.*#EnvironmentFile=${ENV_FILE}#" "${service_target}"
  sed -i "s#^ExecStart=.*#ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/main.py#" "${service_target}"

  install -m 0644 "${INSTALL_DIR}/jarvis.logrotate" "${logrotate_target}"
}

activate_service() {
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"
}

main() {
  require_root
  install_os_packages
  ensure_system_account
  install_application_files
  setup_python_env
  setup_logs
  install_service
  activate_service
  echo "Jarvis installation complete. Service: ${SERVICE_NAME}"
}

main "$@"
