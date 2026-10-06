# Ubuntu 原生部署

本方案在 Ubuntu 24.04 ECS 上使用 Nginx 提供前端静态文件、反向代理 `/api/`，并通过 systemd 保持 FastAPI 后端运行。适用于服务器无法从 Docker Hub 拉取镜像的情况。Windows Server 也可以部署应用，但不适用本目录的 Linux 命令和 systemd 配置。

要求前后端目录分别为 `/home/ecs-user/calculator/calculator_frontend` 和 `/home/ecs-user/calculator/calculator_backend`。以下命令使用 `ecs-user`，如用户名或目录不同，先修改 `calculator-api.service` 中的路径和用户。

```bash
sudo apt-get update
sudo apt-get install -y python3-venv nginx
cd /home/ecs-user/calculator/calculator_backend
python3 -m venv .venv
.venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
sudo install -d -o ecs-user -g ecs-user /var/lib/calculator
sudo install -d /var/www/calculator
sudo cp ../calculator_frontend/index.html ../calculator_frontend/styles.css ../calculator_frontend/app.js ../calculator_frontend/theme.js /var/www/calculator/
sudo cp ../calculator_frontend/config.production.js /var/www/calculator/config.js
sudo cp deployment/ubuntu/calculator-api.service /etc/systemd/system/calculator-api.service
sudo cp deployment/ubuntu/nginx.conf /etc/nginx/sites-available/default
sudo systemctl daemon-reload
sudo systemctl enable --now calculator-api nginx
sudo nginx -t
sudo systemctl reload nginx
curl -f http://127.0.0.1/api/health
```

阿里云安全组入方向需允许 TCP 80，随后访问 `http://服务器公网IP/`。后端只监听 `127.0.0.1:8000`，数据库存于 `/var/lib/calculator/calculator.db`；更新代码时保留该目录。

## 更新代码

将最新的两个仓库文件上传并覆盖到上述目录。若后端依赖有变化，在后端目录运行 `.venv/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt`。然后运行：

```bash
cd /home/ecs-user/calculator/calculator_backend
sudo cp ../calculator_frontend/index.html ../calculator_frontend/styles.css ../calculator_frontend/app.js ../calculator_frontend/theme.js /var/www/calculator/
sudo cp ../calculator_frontend/config.production.js /var/www/calculator/config.js
sudo systemctl restart calculator-api
sudo systemctl is-active calculator-api nginx
curl -f http://127.0.0.1/api/health
```

仅修改 Nginx 配置时，复制新配置后运行 `sudo nginx -t && sudo systemctl reload nginx`。查看故障日志可运行 `sudo journalctl -u calculator-api -n 100 --no-pager` 或 `sudo journalctl -u nginx -n 100 --no-pager`。

