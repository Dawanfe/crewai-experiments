# Reddit Newsletter 生成器

基于 CrewAI 的 Reddit 内容抓取与智能体协作系统，使用 DeepSeek 模型生成技术博客。

## 功能特性

- 自动抓取 Reddit `LocalLLaMA` 子论坛热门帖子与评论
- 三个智能体协作：研究者、写作者、评论者
- 使用 DeepSeek 模型进行内容分析与生成
- 配置文件化管理，无需环境变量

## 配置说明

### 1. 配置文件 (config.json)

```json
{
  "deepseek": {
    "api_key": "你的_deepseek_api_key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "temperature": 0.7
  },
  "reddit": {
    "client_id": "你的_reddit_client_id",
    "client_secret": "你的_reddit_client_secret", 
    "user_agent": "crewai-research-bot",
    "subreddit": "LocalLLaMA",
    "max_posts": 12,
    "max_comments_per_post": 7
  },
  "crewai": {
    "verbose": 2,
    "process": "sequential"
  }
}
```

### 2. 获取 Reddit API 凭据

1. 访问 [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. 点击 "Create App" 或 "Create Another App"
3. 选择 "script" 类型
4. 记录 `client_id` 和 `client_secret`
5. 将凭据填入 `config.json`

### 3. 获取 DeepSeek API 密钥

1. 访问 [DeepSeek 官网](https://platform.deepseek.com/)
2. 注册账号并获取 API 密钥
3. 将密钥填入 `config.json`

## 安装依赖

```bash
pip install praw crewai langchain langchain-openai
```

## 运行

```bash
python3 reddit_newsletter.py
```

### 飞书文档创建工具

#### 功能描述

这个工具可以根据实例代码实现飞书文档创建，并将doc目录中日期最近的文件内容插入到飞书文档中。

#### 主要功能

1. **自动查找最新文档**: 自动扫描`doc`目录，找到日期最新的markdown文件
2. **创建飞书文档**: 使用配置文件中的app_id和app_secret创建新的飞书文档
3. **生成文档链接**: 提供可直接访问的飞书文档链接

#### 使用方法

1. **安装依赖**：

```bash
pip3 install lark_oapi
```

2. **配置设置**：

确保`config.json`文件中包含正确的飞书应用配置：

```json
{
  "feishu": {
    "app_id": "你的应用ID",
    "app_secret": "你的应用密钥",
    "space_id": "空间ID",
    "parent_node_token": "",
    "title_prefix": "AINews"
  }
}
```

3. **运行程序**：

```bash
python3 feishu.py
```

#### 输出结果

程序运行成功后会输出：

- ✅ 飞书文档创建成功！
- 📄 文档链接: https://bytedance.feishu.cn/docx/[文档ID]

#### 注意事项

1. 确保飞书应用有创建文档的权限
2. 确保doc目录中有markdown文件
3. 程序会自动使用最新的markdown文件
4. 生成的文档链接可以直接在浏览器中打开

## 输出格式

脚本会生成包含以下格式的博客文章：

```markdown
## [项目标题](项目链接)
- 有趣的事实
- 与整体主题的关联思考
```

## 注意事项

- 确保 `config.json` 文件存在且格式正确
- Reddit API 有速率限制，脚本会自动处理
- 如 Reddit 凭据缺失，会跳过抓取并返回空结果
- 建议使用 Python 3.10+ 以获得最佳兼容性
- 使用飞书 API 前，请确保已在飞书开放平台为应用开通所需权限（docx 读写、drive 导入、wiki 写入等），并将应用发布可用。