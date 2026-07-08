#!/usr/bin/env bash
# 本地执行：./deploy.sh
# 将项目同步到服务器，自动排除 .gitignore 中的文件（含 .env、*.db 等）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 可选：复制 deploy.local.env.example 为 deploy.local.env 并修改
if [[ -f "$ROOT/deploy.local.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/deploy.local.env"
fi

DEPLOY_HOST="${DEPLOY_HOST:-root@39.107.249.82}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/yi-back-end}"
# 部署后重启；留空则跳过，例如 DEPLOY_RESTART_CMD=""
DEPLOY_RESTART_CMD="${DEPLOY_RESTART_CMD:-systemctl restart myapp}"

if ! command -v rsync >/dev/null 2>&1; then
  echo "错误：未找到 rsync，请先安装（macOS 一般已自带）。" >&2
  exit 1
fi

echo "→ 同步到 ${DEPLOY_HOST}:${DEPLOY_PATH}/"
echo "  排除规则：.gitignore + .git/ + venv/ + deploy.local.env"

rsync -avz \
  --filter=':- .gitignore' \
  --exclude '.git/' \
  --exclude 'venv/' \
  --exclude 'deploy.local.env' \
  --exclude '.DS_Store' \
  "$ROOT/" "${DEPLOY_HOST}:${DEPLOY_PATH}/"

echo "✓ 代码已同步"

if [[ -n "${DEPLOY_RESTART_CMD}" ]]; then
  echo "→ 重启服务：${DEPLOY_RESTART_CMD}"
  ssh "$DEPLOY_HOST" "${DEPLOY_RESTART_CMD}"
  echo "✓ 完成"
else
  echo "→ 未配置 DEPLOY_RESTART_CMD，请自行在服务器重启后端"
fi
