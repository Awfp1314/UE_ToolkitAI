# Cloudflare Tunnel 部署指南

## 前置条件

1. 一个 Cloudflare 账号（免费即可）
2. 域名 `unrealenginetookit.top` 的 NS 已切换到 Cloudflare

## 第一步：将域名 NS 切换到 Cloudflare

这是最关键的一步，必须先完成：

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 点击 "Add a site"，输入 `unrealenginetookit.top`
3. 选择 Free 计划
4. Cloudflare 会给你两个 NS 服务器地址，类似：
   - `xxx.ns.cloudflare.com`
   - `yyy.ns.cloudflare.com`
5. 去腾讯云域名管理，把 DNS 服务器从 DNSPod 改成 Cloudflare 给的这两个
6. 等待 NS 生效（通常几分钟到几小时）

## 第二步：在阿里云服务器上部署

将 `setup_tunnel.sh` 上传到服务器，然后执行：

```bash
chmod +x setup_tunnel.sh
sudo ./setup_tunnel.sh
```

脚本会引导你完成：

- 安装 cloudflared
- 登录 Cloudflare 授权
- 创建隧道
- 配置 DNS 路由

## 第三步：设置为系统服务

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 常用命令

```bash
# 查看隧道状态
cloudflared tunnel list

# 查看服务状态
sudo systemctl status cloudflared

# 查看实时日志
sudo journalctl -u cloudflared -f

# 重启隧道
sudo systemctl restart cloudflared

# 删除隧道（如需重建）
cloudflared tunnel delete ue-toolkit
```

## 注意事项

- 域名 NS 必须先切到 Cloudflare，否则 DNS 路由配置会失败
- 确保 web 服务在 localhost:5000 正常运行
- Cloudflare Tunnel 不需要开放任何入站端口，可以关闭服务器防火墙的 80/443
- 免费计划完全够用，包含 SSL、CDN、基础 DDoS 防护
