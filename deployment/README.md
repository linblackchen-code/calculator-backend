# 两个独立仓库的部署

当前阿里云 ECS 实际采用 Ubuntu 原生部署（Nginx + systemd + Python 虚拟环境），操作说明见 [ubuntu/README.md](ubuntu/README.md)。下面的 Docker 配置仍可用于能访问 Docker Hub 的服务器。

将前端和后端分别克隆或下载到同一父目录，目录名保持如下：

```text
calculator/
├── calculator_frontend/
└── calculator_backend/
    └── deployment/
```

前端仓库的 GitHub 名称可以不同；本地下载目录须使用 `calculator_frontend`，以匹配 Compose 构建路径。

Linux 服务器需要安装 Docker Engine 和 Compose 插件。在本目录运行：

```bash
cp .env.example .env
docker compose config
docker compose up -d --build
docker compose ps
curl -f http://127.0.0.1/api/health
```

默认使用 80 端口，浏览器访问 `http://服务器公网IP`。云平台安全组须允许该端口。只有首次创建配置时复制 `.env`，已有配置时直接编辑。

后端不对外暴露 8000，Nginx 转发 `/api`；SQLite 使用命名卷，普通服务重启和 `docker compose down` 保留数据，`down -v` 会删除数据库。

## 可选 HTTPS

将域名解析到服务器，允许 80/443 入站，并修改 `.env`：

```dotenv
HTTP_BIND=127.0.0.1
HTTP_PORT=8080
DOMAIN=你的实际域名
```

然后执行：

```bash
docker compose -f compose.yaml -f compose.https.yaml up -d --build
```

Caddy 自动申请 HTTPS 证书；启用后使用相同的两个 `-f` 参数管理服务。

此配置已准备，但尚未在公网服务器构建验收。部署后需要实际测试计算、历史保留、删除、收藏和 CSV 导出，并在博客填写真实访问地址。

