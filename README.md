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