"""
脚本用途：
- 使用 PRAW 抓取 Reddit `LocalLLaMA` 板块的热门帖子与评论
- 借助 CrewAI 组织三个智能体（研究者、写作者、评论者）顺序协作
- 产出：基于抓取数据的分析报告与博客草稿，并进行格式与内容把关

注意事项：
- 所有配置参数已移至 config.json 文件中，无需环境变量
- 请在 config.json 中配置 DeepSeek API 密钥和 Reddit 凭据
- 本版本使用 DeepSeek 官方推荐（OpenAI 兼容）方式
"""

import praw
import time
import os
import sys
import json

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from crewai import Agent, Task, Process, Crew


from langchain.agents import load_tools

# 加载配置文件
def load_config():
    """从 config.json 加载配置参数"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("[ERROR] 未找到 config.json 配置文件，请先创建配置文件。")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] 配置文件格式错误: {e}")
        sys.exit(1)

config = load_config()

# 加载「人类介入」工具（Human in the loop），用于在必要时让人类提供输入
human_tools = load_tools(["human"])

# 从配置文件读取 DeepSeek 参数
deepseek_config = config["deepseek"]
deepseek_chat = ChatOpenAI(
    model=deepseek_config["model"],
    openai_api_key=deepseek_config["api_key"],
    openai_api_base=deepseek_config["base_url"],
    temperature=deepseek_config["temperature"],
)


class BrowserTool:
    @tool("Scrape reddit content")
    def scrape_reddit(max_comments_per_post=None):
        """
        抓取 Reddit `LocalLLaMA` 子论坛的热门帖子与评论。

        参数：
        - max_comments_per_post: 每个帖子最多保留的评论数量（默认从配置文件读取）

        返回：
        - 列表，其中每个元素包含：
          {"title": 帖子标题, "url": 帖子链接, "comments": [若干评论文本]}

        注意：
        - 从 config.json 读取 Reddit 配置参数
        - Reddit API 可能会限流；触发异常时会休眠 60 秒重试
        """
        # 从配置文件读取 Reddit 参数
        reddit_config = config["reddit"]
        
        if not reddit_config["client_id"] or not reddit_config["client_secret"] or reddit_config["client_id"] == "your_reddit_client_id":
            print("[WARN] 缺少有效的 Reddit 凭据，使用模拟数据进行演示。")
            return 

        reddit = praw.Reddit(
            client_id=reddit_config["client_id"],
            client_secret=reddit_config["client_secret"],
            password=reddit_config["password"],
            user_agent=reddit_config["user_agent"],
            username=reddit_config["username"],
        )
        reddit.read_only = True
        print('用户名===>', reddit.user.me())
        # 目标子版块：从配置文件读取
        subreddit = reddit.subreddit(reddit_config["subreddit"])
        scraped_data = []

        # 使用配置文件中的参数，并进行类型安全转换
        try:
            max_posts = int(reddit_config["max_posts"]) if reddit_config.get("max_posts") is not None else None
        except (ValueError, TypeError):
            max_posts = None
        try:
            if max_comments_per_post is not None:
                max_comments = int(max_comments_per_post)
            else:
                max_comments = int(reddit_config["max_comments_per_post"]) if reddit_config.get("max_comments_per_post") is not None else None
        except (ValueError, TypeError):
            max_comments = None

        # 抓取热门帖，限制数量以控制速率与时延
        for post in subreddit.hot(limit=max_posts):
            post_data = {"title": post.title, "url": post.url, "comments": []}
            try:
                # 仅加载一层评论，避免深层递归导致速率与复杂度上升
                post.comments.replace_more(limit=0)  # Load top-level comments only
                comments = post.comments.list()
                # 按参数限制评论数量
                if max_comments is not None:
                    comments = comments[:max_comments]

                for comment in comments:
                    post_data["comments"].append(comment.body)

                scraped_data.append(post_data)

            except praw.exceptions.APIException as e:
                print(f"API Exception: {e}")
                time.sleep(60)  # 触发 API 异常时休眠 1 分钟以缓解限流
            except Exception as e:
                print(f"[ERROR] 抓取失败: {e}")
                break

        return scraped_data

"""
代理角色设计：
- explorer（研究者）：利用抓取工具梳理 LocalLLaMA 上的最新有趣项目/公司
- writer（写作者）：基于研究报告撰写面向大众的技术博客
- critic（评论者）：对写作结果进行审阅，确保格式、风格与可读性
"""

explorer = Agent(
    role="高级研究员",
    goal="找到昨天在LocalLLama subreddit上最有趣的项目和公司",
    backstory="""你是一个专家战略家，知道如何在AI、技术和机器学习中识别新兴趋势和公司。
    你在LocalLLama subreddit上很擅长找到有趣的项目。你将抓取的数据转化为详细的报告，其中包含AI/ML世界中最令人兴奋的项目和公司。
    仅使用抓取的数据从LocalLLama subreddit生成报告。
    """,
    verbose=True,
    allow_delegation=False,
    tools=[BrowserTool().scrape_reddit] + human_tools,  # 只允许使用抓取工具与人类介入
    llm=deepseek_chat,
)

writer = Agent(
    role="高级技术作家",
    goal="使用简单、外行的词汇的中文撰写有关最新人工智能项目的引人入胜且有趣的博客文章",
    backstory="""您是一位技术创新领域的专家级作家，尤其擅长人工智能和机器学习领域。您知道如何以引人入胜、趣味盎然、简洁明了的方式写作。您知道如何用通俗易懂的语言，以有趣的方式向普通读者呈现复杂的技术术语。本博客仅使用从 LocalLLama subreddit抓取的数据。""",
    verbose=True,
    allow_delegation=True,
    llm=deepseek_chat,
)
critic = Agent(
    role="文章校对专家",
    goal="提供反馈并批评博客文章草稿。确保语气和写作风格引人入胜、简洁明了。",
    backstory="""您是向技术作家提供反馈的专家。您可以判断博客文章是否简洁、
    简单或不够引人入胜。您知道如何提供有用的反馈来改进任何文本。您知道如何确保文本
    使用外行术语保持技术性和洞察力。
    """,
    verbose=True,
    allow_delegation=True,
    llm=deepseek_chat,
)

task_report = Task(
    description="""使用从 LocalLLaMA 抓取的数据，汇总并输出一份详细报告，聚焦近期上升的 AI 项目。仅可使用抓取到的数据。
    Use and summarize scraped data from subreddit LocalLLama to make a detailed report on the latest rising projects in AI. Use ONLY 
    scraped data from LocalLLama to generate the report. Your final answer MUST be a full analysis report, text only, ignore any code or anything that 
    isn't text. The report has to have bullet points and with 5-10 exciting new AI projects and tools. Write names of every tool and project. 
    Each bullet point MUST contain 3 sentences that refer to one specific ai company, product, model or anything you found on subreddit LocalLLama.  
    """,
    agent=explorer,
)

task_blog = Task(
    description="""撰写纯文本博客：标题短而有力，至少 10 段，面向大众讲解。
    Write a blog article with text only and with a short but impactful headline and at least 10 paragraphs. Blog should summarize 
    the report on latest ai tools found on localLLama subreddit. Style and tone should be compelling and concise, fun, technical but also use 
    layman words for the general public. Name specific new, exciting projects, apps and companies in AI world. Don't 
    write "**Paragraph [number of the paragraph]:**", instead start the new paragraph in a new line. Write names of projects and tools in BOLD.
    ALWAYS include links to projects/tools/research papers. ONLY include information from LocalLLAma.
    For your Outputs use the following markdown format:
    ```
    ## [Title of post](link to project)
    - Interesting facts
    - Own thoughts on how it connects to the overall theme of the newsletter
    ## [Title of second post](link to project)
    - Interesting facts
    - Own thoughts on how it connects to the overall theme of the newsletter
    ```
    """,
    agent=writer,
)

task_critique = Task(
    description="""对输出格式进行把关，若不符合下列 Markdown 模板则需重写：
    The Output MUST have the following markdown format:
    ```
    ## [Title of post](link to project)
    - Interesting facts
    - Own thoughts on how it connects to the overall theme of the newsletter
    ## [Title of second post](link to project)
    - Interesting facts
    - Own thoughts on how it connects to the overall theme of the newsletter
    ```
    Make sure that it does and if it doesn't, rewrite it accordingly.
    """,
    agent=critic,
)

# 从配置文件读取 CrewAI 参数
crewai_config = config["crewai"]

# 组装三位代理与三项任务，顺序执行（前一任务的结果会作为上下文传入下一任务）
crew = Crew(
    agents=[explorer, writer, critic],
    tasks=[task_report, task_blog, task_critique],
    verbose=crewai_config["verbose"],
    process=Process.sequential,  # Sequential process will have tasks executed one after the other and the outcome of the previous one is passed as extra content into this next.
)

# 启动工作流并打印结果
result = crew.kickoff()

print("######################")
print(result)

# 将输出保存到文件（按 年/月 目录，文件名为 年月日.md）
try:
    # 目标目录：doc/YYYY/MM
    year_str = time.strftime("%Y", time.localtime())
    month_str = time.strftime("%m", time.localtime())
    date_str = time.strftime("%Y%m%d", time.localtime())

    doc_dir = os.path.join(os.getcwd(), "doc", year_str, month_str)
    os.makedirs(doc_dir, exist_ok=True)

    # 文件名：YYYYMMDD.md
    newsletter_path = os.path.join(doc_dir, f"{date_str}.md")
    with open(newsletter_path, "w", encoding="utf-8") as f_md:
        f_md.write(str(result))

    # 仍保留原有的运行日志到 output/run.log（若存在则追加，不存在则创建）
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "run.log")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(log_path, "a", encoding="utf-8") as f_log:
        f_log.write(
            f"[{timestamp}] RUN COMPLETED: wrote {newsletter_path} (length={len(str(result))})\n"
        )
    print(f"[INFO] 输出已保存到: {newsletter_path}，运行日志: {log_path}")
except Exception as e:
    print(f"[ERROR] 保存输出失败: {e}")
