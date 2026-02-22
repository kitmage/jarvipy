from pathlib import Path


def test_service_file_has_required_directives() -> None:
    content = Path("jarvis.service").read_text()
    assert "User=jarvis" in content
    assert "Group=jarvis" in content
    assert "WorkingDirectory=/opt/jarvis-pi" in content
    assert "ExecStart=/opt/jarvis-pi/.venv/bin/python /opt/jarvis-pi/main.py" in content
    assert "Restart=on-failure" in content
    assert "EnvironmentFile=/opt/jarvis-pi/.env" in content


def test_logrotate_has_required_policy() -> None:
    content = Path("jarvis.logrotate").read_text()
    assert "daily" in content
    assert "rotate 7" in content
    assert "compress" in content
    assert "copytruncate" in content


def test_install_script_contains_required_setup_steps() -> None:
    content = Path("install.sh").read_text()
    assert "groupadd --system jarvis" in content
    assert "useradd --system" in content
    assert "touch \"${LOG_FILE}\"" in content
    assert "chmod 0640 \"${LOG_FILE}\"" in content
    assert "systemctl enable \"${SERVICE_NAME}\"" in content
    assert "systemctl restart \"${SERVICE_NAME}\"" in content
