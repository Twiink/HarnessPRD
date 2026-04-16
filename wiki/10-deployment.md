# 部署与运维说明

## 本地开发（一键启动）

```bash
git clone <repo>
cd vibecoding
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入 API Key
./start.sh
```

`start.sh` 自动完成：
1. 检查 Python 3.8+ 和 Node.js 18+
2. 创建 Python venv，安装后端依赖
3. 安装前端 npm 依赖
4. 后台启动后端（8000 端口，`--reload` 热重载）
5. 后台启动前端（5173 端口）
6. 打印访问地址，捕获 Ctrl+C 优雅退出

**镜像加速（国内）：**
- pip 使用清华镜像：`https://pypi.tuna.tsinghua.edu.cn/simple/`
- npm 使用淘宝镜像：`https://registry.npmmirror.com`

## 手动启动

### 后端
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # 编辑填入 API Key
uvicorn main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## 生产部署

### 方案一：Nginx 反向代理（推荐）

**架构：**
```
用户 → Nginx (443) → 前端静态文件 (build/)
                   → /api/* → FastAPI (8000)
```

**前端构建：**
```bash
cd frontend
npm run build
# 产物在 frontend/dist/
```

**Nginx 配置：**
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    # SSL 证书
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端静态文件
    root /path/to/vibecoding/frontend/dist;
    index index.html;

    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 流式响应必须禁用缓冲
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

**后端生产启动（使用 Gunicorn）：**
```bash
pip install gunicorn
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

> SSE 流式响应在 Nginx 后面必须设置 `proxy_buffering off`，否则流式输出会被缓冲，用户看不到实时效果。

### 方案二：Docker（推荐用于快速部署）

**后端 Dockerfile：**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**前端 Dockerfile（多阶段构建）：**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci --registry https://registry.npmmirror.com
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**docker-compose.yml：**
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    env_file: ./backend/.env
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
```

## 进程管理（生产环境）

使用 systemd 或 supervisor 管理后端进程：

**systemd 示例（`/etc/systemd/system/vibecoding.service`）：**
```ini
[Unit]
Description=VibeCoding Backend
After=network.target

[Service]
Type=exec
User=www-data
WorkingDirectory=/path/to/vibecoding/backend
ExecStart=/path/to/vibecoding/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable vibecoding
systemctl start vibecoding
systemctl status vibecoding
```

## 监控与日志

### 健康检查
```bash
curl http://localhost:8000/health
# {"status": "ok", "message": "Vibe Coding API is running"}
```

### 日志
Uvicorn 默认输出到 stdout，包含请求日志。
生产环境重定向到文件：
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 >> /var/log/vibecoding.log 2>&1
```

### 关键监控指标
- API 响应时间（SSE 首字节时间）
- LLM API 调用错误率（`/api/conversation/*` 接口的错误 SSE 事件）
- 后端进程存活（健康检查接口）

## 安全注意事项

### API Key 安全
- `.env` 文件不提交 git（`.gitignore` 已配置）
- 生产环境使用环境变量或密钥管理服务（如 AWS Secrets Manager）
- `GET /api/config/current` 接口不返回 API Key 明文

### 访问控制
目前无用户认证，**所有人访问都可以触发 LLM 调用**。

生产环境建议：
- 在 Nginx 层加 IP 白名单 或 Basic Auth
- 或添加后端 API Key 验证中间件

### CORS
生产环境必须将 `CORS_ORIGINS` 设置为真实域名，而非 `*`：
```env
CORS_ORIGINS=https://your-domain.com
```

## 版本更新

```bash
git pull origin main

# 更新后端依赖
cd backend
.venv/bin/pip install -r requirements.txt

# 更新前端依赖
cd frontend
npm install

# 重启服务
systemctl restart vibecoding   # 后端
# 前端若有变更需重新 build 并部署到 Nginx
npm run build
```
