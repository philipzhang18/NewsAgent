# News Agent 启动说明

## 快速开始

### 1. 环境准备

确保您的系统已安装：
- Python 3.8+
- pip
- Git

### 2. 克隆项目

```bash
git clone https://github.com/philipzhang18/NewsAgent.git
cd newsagent
```

### 3. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python -m venv venv
source venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 配置环境变量

复制环境变量示例文件：
```bash
# Windows
copy env.example .env

# Linux/macOS
cp env.example .env
```

编辑 `.env` 文件，填入必要的API密钥：

```env
# 必需配置
OPENAI_API_KEY=your_openai_api_key_here          
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
NEWS_API_KEY=your_newsapi_key_here               0683db8707b74a3ab4e5179120a407be

# 可选配置
FLASK_SECRET_KEY=your_secret_key_here
DEBUG=True
LOG_LEVEL=INFO
```

### 6. 获取API密钥

#### OpenAI API Key
1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 注册账户并登录
3. 在API Keys页面创建新的API密钥
4. 复制密钥到 `.env` 文件

#### News API Key
1. 访问 [NewsAPI](https://newsapi.org/)
2. 注册免费账户
3. 获取API密钥
4. 复制密钥到 `.env` 文件

### 7. 运行应用

```bash
python run.py
```

应用将在 `http://localhost:5000` 启动

## 功能特性

### 新闻收集
- **RSS源**: 自动从配置的RSS源收集新闻
- **多源支持**: 支持BBC、CNN、Reuters等主流新闻源
- **定时收集**: 可配置收集间隔时间

### 内容分析
- **情感分析**: 使用OpenAI分析新闻情感倾向
- **偏见检测**: 识别潜在的新闻偏见和不可靠信息
- **5W1H提取**: 自动提取新闻的关键要素

### 智能处理
- **自动摘要**: 生成新闻摘要
- **关键词提取**: 自动识别重要标签
- **语言检测**: 支持多语言新闻

## 配置选项

### 收集设置
```env
# 收集间隔（秒）
COLLECTION_INTERVAL=300

# 每个源的最大文章数
MAX_ARTICLES_PER_SOURCE=100

# 启用的RSS源
RSS_FEEDS=https://feeds.bbci.co.uk/news/rss.xml,https://rss.cnn.com/rss/edition.rss
```

### 功能开关
```env
# 启用情感分析
ENABLE_SENTIMENT_ANALYSIS=True

# 启用偏见检测
ENABLE_BIAS_DETECTION=True
```

### 数据库配置
```env
# MongoDB连接字符串
MONGODB_URI=mongodb://localhost:27017/news_agent

# Redis连接字符串
REDIS_URL=redis://localhost:6379
```

## 使用说明

### Web界面
1. 打开浏览器访问 `http://localhost:5000`
2. 使用侧边栏导航不同功能页面
3. 在"Service Control"中管理新闻收集服务

### API接口
- `GET /api/news/status` - 获取服务状态
- `GET /api/news/articles` - 获取新闻文章
- `POST /api/news/collect` - 触发新闻收集
- `POST /api/news/process` - 处理文章分析

### 监控和统计
- 实时监控收集状态
- 查看收集统计信息
- 分析情感分布
- 跟踪源分布

## 故障排除

### 常见问题

#### 1. 配置验证失败
```
Missing required environment variables: OPENAI_API_KEY, NEWS_API_KEY
```
**解决方案**: 检查 `.env` 文件中的API密钥配置

#### 2. 依赖安装失败
```
ERROR: Could not find a version that satisfies the requirement
```
**解决方案**: 升级pip版本或使用国内镜像源
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements.txt
```

#### 3. 端口被占用
```
Address already in use
```
**解决方案**: 更改端口或停止占用端口的进程
```bash
# 在run.py中修改端口
app.run(host='0.0.0.0', port=5001, debug=settings.DEBUG)
```

#### 4. 新闻收集失败
```
Error collecting from RSS feed
```
**解决方案**: 
- 检查网络连接
- 验证RSS源URL是否有效
- 查看日志文件获取详细错误信息

### 日志查看
应用运行时会生成 `news_agent.log` 日志文件，包含详细的运行信息：

```bash
# 实时查看日志
tail -f news_agent.log

# 查看错误日志
grep "ERROR" news_agent.log
```

## 高级配置

### 自定义RSS源
在 `.env` 文件中添加更多RSS源：

```env
RSS_FEEDS=https://feeds.bbci.co.uk/news/rss.xml,https://rss.cnn.com/rss/edition.rss,https://feeds.reuters.com/reuters/topNews,https://your-custom-feed.com/rss
```

### 调整收集频率
```env
# 每5分钟收集一次
COLLECTION_INTERVAL=300

# 每小时收集一次
COLLECTION_INTERVAL=3600
```

### 启用调试模式
```env
DEBUG=True
LOG_LEVEL=DEBUG
```

## 生产部署

### 使用Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### 使用Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "run.py"]
```

### 反向代理配置
使用Nginx作为反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 技术支持

如果遇到问题，请：
1. 查看日志文件
2. 检查配置文件
3. 验证API密钥
4. 查看GitHub Issues

## 更新日志

### v1.0.0
- 初始版本发布
- 支持RSS新闻收集
- 集成OpenAI分析
- 提供Web管理界面






