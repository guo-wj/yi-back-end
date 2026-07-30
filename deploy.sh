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

LOCAL_PALM_MD5="$(md5 -q "$ROOT/services/palm_extractor.py" 2>/dev/null || md5sum "$ROOT/services/palm_extractor.py" | awk '{print $1}')"

echo "→ 同步到 ${DEPLOY_HOST}:${DEPLOY_PATH}/"
echo "  排除规则：.gitignore + .git/ + venv/ + deploy.local.env"
echo "  本地 palm_extractor.md5=${LOCAL_PALM_MD5}"

# -i 列出每个变更文件；--delete 不默认开启，避免误删服务器 .env / 数据
rsync -avzi \
  --filter=':- .gitignore' \
  --exclude '.git/' \
  --exclude 'venv/' \
  --exclude 'deploy.local.env' \
  --exclude '.DS_Store' \
  "$ROOT/" "${DEPLOY_HOST}:${DEPLOY_PATH}/"

echo "✓ 代码已同步"

echo "→ 校验远端文件并清理缓存"
ssh "$DEPLOY_HOST" bash -s <<EOF
set -euo pipefail
cd "${DEPLOY_PATH}"
REMOTE_MD5=\$(md5sum services/palm_extractor.py | awk '{print \$1}')
echo "  远端 palm_extractor.md5=\${REMOTE_MD5}"
if [[ "\${REMOTE_MD5}" != "${LOCAL_PALM_MD5}" ]]; then
  echo "✗ 远端文件与本地不一致，部署可能失败" >&2
  exit 1
fi
if ! grep -q '_LINE_HINTS' services/palm_extractor.py; then
  echo "✗ 远端仍是旧版 palm_extractor（缺少 _LINE_HINTS）" >&2
  exit 1
fi
find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete 2>/dev/null || true
echo "  已清理 __pycache__"
EOF

if [[ -n "${DEPLOY_RESTART_CMD}" ]]; then
  echo "→ 强制重启（停旧 uvicorn + ${DEPLOY_RESTART_CMD}）"
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -euo pipefail
systemctl stop myapp 2>/dev/null || true
pkill -f 'uvicorn app:app' 2>/dev/null || true
sleep 1
${DEPLOY_RESTART_CMD}
sleep 1
ps aux | grep -E 'uvicorn app:app' | grep -v grep || {
  echo "✗ 重启后未发现 uvicorn 进程" >&2
  exit 1
}
curl -sf http://127.0.0.1:8000/health >/dev/null && echo "  health ok" || echo "  警告：本机 :8000/health 不通（若经 nginx 可忽略）"
EOF
  echo "✓ 完成"
else
  echo "→ 未配置 DEPLOY_RESTART_CMD，请自行在服务器重启后端"
fi
