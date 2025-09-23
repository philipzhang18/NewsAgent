# News Agent 项目结构

## 目录结构

```
news-agent/
├── 📁 src/                          # 源代码目录
│   ├── 📁 api/                      # API接口层
│   │   ├── __init__.py
│   │   └── news_api.py             # 新闻API端点
│   ├── 📁 collectors/              # 新闻收集器
│   │   ├── __init__.py
│   │   ├── base_collector.py       # 基础收集器类
│   │   └── rss_collector.py        # RSS收集器实现
│   ├── 📁 config/                  # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py             # 应用配置设置
│   ├── 📁 models/                  # 数据模型
│   │   ├── __init__.py
│   │   └── news_models.py          # 新闻数据模型
│   ├── 📁 processors/              # 新闻处理器
│   │   ├── __init__.py
│   │   └── news_processor.py       # 新闻内容处理器
│   ├── 📁 services/                # 核心服务
│   │   ├── __init__.py
│   │   └── news_collector_service.py # 新闻收集服务
│   ├── 📁 templates/               # HTML模板
│   │   ├── base.html               # 基础模板
│   │   └── dashboard.html          # 仪表板页面
│   ├── __init__.py                 # 包初始化
│   └── app.py                      # Flask主应用
├── 📄 requirements.txt              # Python依赖包
├── 📄 env.example                  # 环境变量示例
├── 📄 README.md                    # 项目说明文档
├── 📄 STARTUP.md                   # 启动说明文档
├── 📄 PROJECT_STRUCTURE.md         # 项目结构说明
├── 📄 config.py                    # 配置管理
├── 📄 run.py                       # 主启动脚本
└── 📄 test_news_agent.py           # 测试脚本
```

## 架构设计

### 1. 分层架构

```
┌─────────────────────────────────────┐
│           Web Interface            │  ← Flask + Bootstrap
├─────────────────────────────────────┤
│           API Layer                │  ← RESTful API
├─────────────────────────────────────┤
│         Service Layer              │  ← Business Logic
├─────────────────────────────────────┤
│      Processor Layer               │  ← Content Analysis
├─────────────────────────────────────┤
│      Collector Layer               │  ← News Collection
├─────────────────────────────────────┤
│         Model Layer                │  ← Data Models
├─────────────────────────────────────┤
│      Configuration Layer           │  ← Settings & Config
└─────────────────────────────────────┘
```

### 2. 核心组件

#### 新闻收集器 (Collectors)
- **BaseCollector**: 抽象基类，定义收集器接口
- **RSSCollector**: RSS源新闻收集器
- **APICollector**: 新闻API收集器（可扩展）
- **WebScraper**: 网页爬虫收集器（可扩展）

#### 新闻处理器 (Processors)
- **NewsProcessor**: 核心内容处理器
- **SentimentAnalyzer**: 情感分析器
- **BiasDetector**: 偏见检测器
- **5W1HExtractor**: 关键信息提取器

#### 核心服务 (Services)
- **NewsCollectorService**: 新闻收集协调服务
- **NewsProcessorService**: 新闻处理协调服务
- **StorageService**: 数据存储服务（可扩展）

#### 数据模型 (Models)
- **NewsArticle**: 新闻文章模型
- **NewsSource**: 新闻源模型
- **NewsCollection**: 新闻收集批次模型
- **SentimentType**: 情感类型枚举

### 3. 数据流

```
RSS Feeds → RSSCollector → NewsArticle → NewsProcessor → Analyzed Article
    ↓              ↓            ↓              ↓              ↓
Validation → Collection → Processing → Analysis → Storage/Display
```

### 4. 技术栈

#### 后端
- **Python 3.8+**: 主要编程语言
- **Flask**: Web框架
- **asyncio**: 异步编程支持
- **OpenAI API**: AI内容分析
- **NLTK**: 自然语言处理
- **TextBlob**: 文本分析

#### 前端
- **Bootstrap 5**: UI框架
- **Chart.js**: 数据可视化
- **Font Awesome**: 图标库
- **jQuery**: JavaScript库

#### 数据存储
- **MongoDB**: 主数据库（可扩展）
- **Redis**: 缓存和队列（可扩展）

## 模块说明

### API模块 (`src/api/`)
提供RESTful API接口，包括：
- 新闻文章查询
- 服务状态监控
- 手动触发收集
- 文章处理请求

### 收集器模块 (`src/collectors/`)
负责从各种源收集新闻：
- 支持RSS源
- 可扩展其他源类型
- 异步收集处理
- 错误处理和重试

### 处理器模块 (`src/processors/`)
处理和分析新闻内容：
- 文本清理和标准化
- 情感分析
- 偏见检测
- 关键信息提取
- 自动摘要生成

### 服务模块 (`src/services/`)
协调各个组件的工作：
- 收集器管理
- 处理流程控制
- 状态监控
- 统计信息收集

### 模型模块 (`src/models/`)
定义数据结构：
- 新闻文章模型
- 新闻源模型
- 收集批次模型
- 枚举类型定义

### 配置模块 (`src/config/`)
管理应用配置：
- 环境变量加载
- 配置验证
- 默认值设置
- 配置分类管理

## 扩展性设计

### 1. 新收集器类型
```python
class CustomCollector(BaseCollector):
    async def collect_news(self):
        # 实现自定义收集逻辑
        pass
    
    async def validate_source(self):
        # 实现源验证逻辑
        pass
```

### 2. 新处理器类型
```python
class CustomProcessor:
    async def process(self, article):
        # 实现自定义处理逻辑
        pass
```

### 3. 新数据源
```python
# 在settings.py中添加
CUSTOM_SOURCES = [
    "https://custom-news-source.com/feed",
    "https://another-source.com/rss"
]
```

### 4. 新分析功能
```python
class CustomAnalyzer:
    async def analyze(self, article):
        # 实现自定义分析逻辑
        pass
```

## 部署架构

### 开发环境
```
┌─────────────────┐
│   Flask Dev     │
│   Server        │
└─────────────────┘
```

### 生产环境
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx         │    │   Gunicorn      │    │   MongoDB       │
│   (Reverse      │───▶│   (WSGI         │───▶│   (Database)    │
│   Proxy)        │    │   Server)       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 监控和日志

### 日志级别
- **DEBUG**: 详细调试信息
- **INFO**: 一般信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

### 监控指标
- 收集成功率
- 处理性能
- API响应时间
- 错误率统计
- 资源使用情况

## 安全考虑

### 1. API安全
- 环境变量配置
- 输入验证
- 错误信息过滤
- 速率限制（可扩展）

### 2. 数据安全
- 敏感信息加密
- 访问控制
- 数据备份
- 审计日志

### 3. 网络安全
- HTTPS支持
- CORS配置
- 防火墙规则
- 定期安全更新

## 性能优化

### 1. 异步处理
- 使用asyncio进行异步操作
- 并发收集和处理
- 非阻塞I/O操作

### 2. 缓存策略
- Redis缓存热点数据
- 内存缓存频繁访问的数据
- 智能缓存失效策略

### 3. 数据库优化
- 索引优化
- 查询优化
- 连接池管理
- 读写分离（可扩展）

## 故障恢复

### 1. 错误处理
- 优雅降级
- 自动重试机制
- 错误日志记录
- 用户友好错误信息

### 2. 备份策略
- 定期数据备份
- 配置备份
- 代码版本控制
- 灾难恢复计划

### 3. 监控告警
- 服务状态监控
- 性能指标监控
- 异常告警机制
- 自动恢复尝试






