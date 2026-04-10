# 部署指南

## 生产环境部署

### 1. Docker 部署（推荐）

#### 构建镜像

```bash
# 构建后端镜像
docker build -t literature-workflow-backend ./backend

# 构建前端镜像
docker build -t literature-workflow-frontend ./frontend
```

#### 运行容器

```bash
# 启动后端
docker run -d \
  --name workflow-backend \
  -p 8000:8000 \
  -v $(pwd)/output:/app/output \
  -e ANTHROPIC_API_KEY=your_key \
  -e ANTHROPIC_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
  literature-workflow-backend

# 启动前端
docker run -d \
  --name workflow-frontend \
  -p 80:80 \
  -e VITE_API_BASE_URL=http://localhost:8000 \
  literature-workflow-frontend
```

### 2. Docker Compose 部署

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./output:/app/output
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}
      - DATABASE_URL=sqlite+aiosqlite:///output/workflow_store.db
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped
```

运行：

```bash
docker-compose up -d
```

### 3. 直接使用 Uvicorn 部署

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动（多进程）
uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
```

### 4. 使用 Gunicorn 部署

```bash
# 安装
pip install gunicorn

# 启动
gunicorn backend.app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log
```

### 5. Nginx 反向代理

配置 Nginx：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /var/www/literature-workflow;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 代理
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ANTHROPIC_API_KEY` | LLM API Key | - |
| `ANTHROPIC_BASE_URL` | API 基础 URL | https://dashscope.aliyuncs.com |
| `HOST` | 后端监听地址 | 0.0.0.0 |
| `PORT` | 后端监听端口 | 8000 |
| `DEBUG` | 调试模式 | false |
| `DATABASE_URL` | 数据库连接 | sqlite:///output/workflow_store.db |
| `VITE_API_BASE_URL` | 前端 API 地址 | /api |

## 性能优化

### 后端优化

1. **使用 uvloop 和 httptools**
```bash
pip install uvloop httptools
uvicorn ... --loop uvloop --http httptools
```

2. **调整 worker 数量**
```bash
# worker 数 = (CPU 核心数 * 2) + 1
uvicorn ... --workers 9
```

3. **启用数据库 WAL 模式**（已默认启用）

### 前端优化

1. **生产构建**
```bash
npm run build
```

2. **启用 gzip 压缩**
```nginx
gzip on;
gzip_types text/plain application/json text/css application/javascript;
```

3. **静态资源缓存**
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## 监控和日志

### 日志配置

```python
# 使用 logging 模块
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
```

### 健康检查

```bash
curl http://localhost:8000/health
```

### 性能监控

推荐使用：
- Prometheus + Grafana - 指标监控
- Jaeger - 分布式追踪
- ELK Stack - 日志分析

## 故障排除

### 常见问题

1. **后端启动失败**
   - 检查端口占用：`lsof -i:8000`
   - 检查环境变量配置
   - 查看错误日志

2. **WebSocket 连接失败**
   - 确认 Nginx WebSocket 配置正确
   - 检查防火墙设置
   - 验证协议升级头

3. **数据库锁定**
   - 确保使用 WAL 模式
   - 减少并发写入
   - 考虑迁移到 PostgreSQL

### 恢复数据

```bash
# 备份数据库
cp output/workflow_store.db backup.db

# 恢复
cp backup.db output/workflow_store.db
```
