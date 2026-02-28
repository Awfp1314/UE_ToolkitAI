#!/bin/bash
# Cloudflare Tunnel 一键部署脚本
# 使用方法: chmod +x setup_tunnel.sh && sudo ./setup_tunnel.sh

set -e

TUNNEL_NAME="ue-toolkit"
DOMAIN="unrealenginetookit.top"
LOCAL_PORT=5000

echo "========================================="
echo "  Cloudflare Tunnel 部署脚本"
echo "========================================="

# 1. 安装 cloudflared
echo ""
echo "[1/5] 安装 cloudflared..."
if command -v cloudflared &> /dev/null; then
    echo "cloudflared 已安装，跳过"
else
    # 检测系统架构
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
    else
        echo "不支持的架构: $ARCH"
        exit 1
    fi
    curl -L "$CLOUDFLARED_URL" -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    echo "cloudflared 安装完成"
fi

cloudflared --version

# 2. 登录 Cloudflare
echo ""
echo "[2/5] 登录 Cloudflare 账号..."
echo "执行后会弹出一个 URL，复制到浏览器中完成授权"
echo ""
cloudflared tunnel login

# 3. 创建隧道
echo ""
echo "[3/5] 创建隧道: $TUNNEL_NAME"
cloudflared tunnel create $TUNNEL_NAME

# 获取隧道 ID
TUNNEL_ID=$(cloudflared tunnel list | grep $TUNNEL_NAME | awk '{print $1}')
echo "隧道 ID: $TUNNEL_ID"

# 4. 创建配置文件
echo ""
echo "[4/5] 生成配置文件..."
mkdir -p /etc/cloudflared

cat > /etc/cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json

ingress:
  # 主域名 -> 本地 web 服务
  - hostname: $DOMAIN
    service: http://localhost:$LOCAL_PORT
  # www 子域名
  - hostname: www.$DOMAIN
    service: http://localhost:$LOCAL_PORT
  # API 子域名（如果需要单独的 API 域名）
  - hostname: api.$DOMAIN
    service: http://localhost:$LOCAL_PORT
  # 兜底规则（必须有）
  - service: http_status:404
EOF

echo "配置文件已写入 /etc/cloudflared/config.yml"

# 5. 配置 DNS 路由
echo ""
echo "[5/5] 配置 DNS 路由..."
cloudflared tunnel route dns $TUNNEL_NAME $DOMAIN
cloudflared tunnel route dns $TUNNEL_NAME www.$DOMAIN
cloudflared tunnel route dns $TUNNEL_NAME api.$DOMAIN

echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "手动启动隧道（测试用）:"
echo "  cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "安装为系统服务（推荐）:"
echo "  sudo cloudflared service install"
echo "  sudo systemctl enable cloudflared"
echo "  sudo systemctl start cloudflared"
echo ""
echo "查看状态:"
echo "  sudo systemctl status cloudflared"
echo ""
echo "查看日志:"
echo "  sudo journalctl -u cloudflared -f"
echo ""
echo "注意: 请确保你的 web 服务已在 localhost:$LOCAL_PORT 上运行"
