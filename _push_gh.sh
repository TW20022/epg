#!/bin/bash
# 一次性：把精简后的方案推到 GitHub TW20022/epg 的 main 分支
set -e
SRC=/mnt/c/Users/Administrator/WorkBuddy/2026-11-08-19-24-05/epg
D=/home/opc/epg-gh
mkdir -p "$D"
cp -r "$SRC/." "$D/"
cd "$D"

echo "=== 待推送文件 ==="
find . -type f -not -path './.git/*' | sort

if [ ! -d .git ]; then git init -q; fi
git branch -M main
if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin https://github.com/TW20022/epg.git
fi
git add -A
git commit -q -m "feat: GitHub Actions 云端构建去广告 EPG（单 YAML）"
echo "=== 提交 ==="
git log -1 --oneline

echo "=== 推送 ==="
if GIT_TERMINAL_PROMPT=0 git push -u origin main > /tmp/epg_gh_push.log 2>&1; then
    echo "按用户指定地址（HTTPS）推送成功"
else
    echo "HTTPS 无凭据，改用本机已认证的 SSH key："
    git remote set-url origin git@github.com:TW20022/epg.git
    git push -u origin main
fi

echo "=== remote / 状态 ==="
git remote -v
git status -sb
