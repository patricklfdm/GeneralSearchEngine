#!/usr/bin/env bash
# Run as root ONLY inside the dedicated GSE-Runner Ubuntu 24.04 WSL2 distro.
# Registration is deliberately separate: no GitHub token is accepted here.
set -euo pipefail
umask 077
[[ $(id -u) = 0 && ${WSL_DISTRO_NAME:-} = GSE-Runner ]]
. /etc/os-release
[[ $ID = ubuntu && $VERSION_ID = 24.04 ]]
export DEBIAN_FRONTEND=noninteractive
# The Runner only initiates outbound SSH. Keep the server binary available for
# loopback checks, but never start a listener on the shared WSL network.
systemctl mask ssh.service ssh.socket
dpkg --configure -a
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git unzip zip xz-utils tar \
  python3 python3-venv openssh-client openssh-server rsync jq gh maven \
  libicu74 libssl3t64 libkrb5-3 libzstd1 zlib1g
if ! id gse-runner >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash gse-runner
fi
chmod 700 /home/gse-runner
install -d -m 700 -o gse-runner -g gse-runner \
  /home/gse-runner/actions-runner /home/gse-runner/actions-runner/_work \
  /home/gse-runner/actions-runner/_work/_tool \
  /home/gse-runner/evidence-archives /home/gse-runner/runner-state
install -d -m 755 /opt/gse-runner /etc/gse-runner
version=2.338.0
runner_sha=af4b794c1bc41d73d40535e3fe092a39f9679cd8d965954c2aca25a05ca41d32
package=/var/tmp/gse-actions-runner-$version.tar.gz
if [[ ! -f /home/gse-runner/actions-runner/config.sh ]]; then
  curl --fail --location --retry 3 --connect-timeout 30 \
    "https://github.com/actions/runner/releases/download/v$version/actions-runner-linux-x64-$version.tar.gz" \
    --output "$package"
  printf '%s  %s\n' "$runner_sha" "$package" | sha256sum --check
  tar -xzf "$package" -C /home/gse-runner/actions-runner
  chown -R gse-runner:gse-runner /home/gse-runner/actions-runner
fi
cat > /etc/gse-runner/host.json <<'JSON'
{"schema":"gse-v52-self-hosted-v1","name":"gse-v52-cloud-d-wsl","workspaceRoot":"/home/gse-runner/actions-runner/_work","archiveRoot":"/home/gse-runner/evidence-archives","stateRoot":"/home/gse-runner/runner-state","backingStore":"D:\\GSE-Runner\\Ubuntu"}
JSON
chmod 644 /etc/gse-runner/host.json
cat > /opt/gse-runner/started.sh <<'SH'
#!/bin/bash
set -euo pipefail
umask 077
exec /usr/bin/python3 /opt/gse-runner/cloud_self_hosted.py started
SH
cat > /opt/gse-runner/completed.sh <<'SH'
#!/bin/bash
set -euo pipefail
umask 077
exec /usr/bin/python3 /opt/gse-runner/cloud_self_hosted.py completed
SH
chmod 755 /opt/gse-runner/started.sh /opt/gse-runner/completed.sh
cat > /home/gse-runner/actions-runner/.env <<'ENV'
ACTIONS_RUNNER_HOOK_JOB_STARTED=/opt/gse-runner/started.sh
ACTIONS_RUNNER_HOOK_JOB_COMPLETED=/opt/gse-runner/completed.sh
RUNNER_TOOL_CACHE=/home/gse-runner/actions-runner/_work/_tool
LANG=C.UTF-8
ENV
chown root:gse-runner /home/gse-runner/actions-runner/.env
chmod 640 /home/gse-runner/actions-runner/.env
cat > /etc/wsl.conf <<'CONF'
[boot]
systemd=true
[user]
default=gse-runner
[automount]
enabled=false
[interop]
enabled=false
appendWindowsPath=false
CONF
chmod 644 /etc/wsl.conf
echo 'Dedicated Runner dependencies installed; deploy hook module, restart this distro, then register.'
