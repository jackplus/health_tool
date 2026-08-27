# 个人运动健康数据中心

自托管的个人运动健康数据中心：通过 Health Auto Export 定期接收 Apple Health 数据，生成基于个人基线的每日/每周建议，并通过只读 MCP 工具向 Codex 等 AI Agent 提供受控分析能力。保留 Apple Health 全量 ZIP 与小米运动健康文件的手动导入作为历史回填渠道。

## 数据流

Apple Health 没有供自托管服务直接拉取个人 HealthKit 数据的云端 API。本项目采用推送方式：

1. iPhone 上的 Health Auto Export 定期把选定指标和运动记录发送到私有 API。
2. API 校验密钥、标准化数据并幂等写入 PostgreSQL。
3. 独立 scheduler 每天和每周生成可解释的个人基线报告。
4. Streamlit 展示数据与建议；Codex 通过只读 MCP 工具查询聚合结果。

重复推送或重复上传是安全的。API 按负载哈希审计请求，指标与运动记录另有数据库唯一约束。

## 架构

- `db`：PostgreSQL，存储指标、运动、摄取审计、规则报告、个人目标和 MCP 审计。
- `api`：FastAPI，接收 Health Auto Export JSON。
- `scheduler`：APScheduler，按 Asia/Shanghai 时区生成每日及每周报告。
- `app`：Streamlit 看板与手动回填入口。
- `mcp`：只读 MCP Server，为 Codex 提供有界聚合查询。

```
health_tool/
  docker-compose.yml
  Dockerfile
  db/schema.sql
  app/
    main.py                 # Streamlit 入口
    pages/                  # Overview / Trends / Workouts / Upload / Settings
    config.py / db.py / queries.py / ingestion.py / style.py
    parsers/
      apple_health.py       # export.xml 流式解析
      health_auto_export.py # Health Auto Export JSON 标准化
      xiaomi.py             # 小米导出的尽力而为适配层
    api.py / worker.py / analysis.py / mcp_server.py
```

## 运行方式

项目使用 Docker Compose 同时启动 PostgreSQL 和 Streamlit，不需要在本机单独安装 Python 或 PostgreSQL。

### 1. 准备运行环境

请先安装并启动 Docker：

- macOS / Windows：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。
- Linux：安装 Docker Engine 和 Docker Compose 插件。

确认 Docker 可用：

```bash
docker --version
docker compose version
```

### 2. 进入项目目录

如果还没有下载项目，先执行：

```bash
git clone https://github.com/jackplus/health_tool.git
cd health_tool
```

如果已经下载，直接在终端进入包含 `docker-compose.yml` 的项目根目录。

### 3. 创建环境变量文件

```bash
cp .env.example .env
```

打开 `.env`，至少修改数据库密码并生成一个长随机 API 密钥：

```dotenv
POSTGRES_USER=health
POSTGRES_PASSWORD=请替换为强密码
POSTGRES_DB=health
POSTGRES_HOST=db
POSTGRES_PORT=5432
APP_TIMEZONE=Asia/Shanghai
HEALTH_API_KEY=请替换为长随机字符串
```

`.env` 已被 `.gitignore` 忽略，不要将真实密码提交到 Git。

### 4. 构建并启动服务

```bash
docker compose up -d --build
```

首次启动会下载镜像、安装 Python 依赖并初始化数据库，所需时间取决于网络速度。

查看服务状态：

```bash
docker compose ps
```

正常情况下，`db` 和 `api` 应显示为 `healthy`，`app` 与 `scheduler` 应显示为运行中。如果启动失败，查看日志：

```bash
docker compose logs -f app
docker compose logs -f db
docker compose logs -f api
docker compose logs -f scheduler
```

按 `Ctrl+C` 可退出日志查看，不会停止服务。

### 5. 打开看板

本机运行时，在浏览器打开：

```text
http://localhost:8501
```

如果 Docker 运行在另一台服务器上，将 `localhost` 替换为服务器 IP 或域名。健康数据属于敏感信息，请不要将 8501 端口直接暴露到公网；远程部署时应使用 HTTPS 和身份认证。

## 配置 iPhone 自动同步

在 Health Auto Export 中创建两条 REST API 自动化：

1. URL：`http://家中服务器IP:3001/api/v1/health-auto-export`。
2. 请求头：`api-key`，值与 `.env` 的 `HEALTH_API_KEY` 完全相同。
3. 健康指标自动化选择睡眠、步数、活动能量、静息心率、HRV、体重；有数据时选择 VO₂max。格式使用 JSON，按天聚合并启用批量请求。
4. 运动自动化选择 Workouts，保留单次运动详情；服务端不会向 Agent 暴露 GPS 路线。
5. 先用 Manual Export 发送一段历史范围，再启用每日自动化。

服务器必须在 iPhone 发送时在线。当前配置只应在可信家庭局域网内使用，不要把 3001 端口直接暴露到公网。

## 手动历史回填

### Apple Health

1. 在 iPhone 上打开「健康」App。
2. 点击右上角头像。
3. 选择「导出所有健康数据」，确认导出。
4. 等待系统生成 `export.zip`，再通过 AirDrop、iCloud Drive 或其他安全方式传到电脑。
5. 在看板左侧导航中打开 **Upload**。
6. 选择 **Apple Health** 标签页，点击上传区域并选择原始 `export.zip`。不要先解压。
7. 点击「解析并导入」，等待页面显示解析数量和新写入数量。导出文件较大时可能需要几分钟。

导入完成后，可以在 **Overview**、**Trends** 和 **Workouts** 页面查看数据。重复上传同一份 Apple Health 全量导出时，已存在的记录会被跳过。

### 小米运动健康

1. 在小米运动健康 App 中申请导出个人数据。具体入口可能会随 App 版本和地区变化。
2. 导出完成后，将获得的 `.csv`、`.json` 或包含这些文件的 `.zip` 传到电脑。
3. 在看板左侧导航中打开 **Upload**。
4. 选择 **小米运动健康** 标签页，选择文件后点击「解析并导入」。
5. 检查页面显示的指标类型、解析数量和未识别说明，再到 **Overview** 或 **Trends** 页面核对数值。

小米没有公开文档化的个人数据导出格式，因此当前解析器会根据常见文件名和列名尽力识别。首次导入后请务必与 App 中的原始数值进行抽样核对。

### 查看上传结果

**Upload** 页面底部的「上传历史」会显示：

- 数据来源和文件名；
- 上传时间与处理状态；
- 解析记录数和实际新写入数；
- 重复数据或无法识别内容的说明。

上传的原始文件会保存在项目的 `data/uploads/` 目录中。请注意该目录包含敏感个人数据，需做好访问权限和备份保护。

## 停止、重启和更新

停止并删除当前容器（保留数据库卷和上传文件）：

```bash
docker compose down
```

重启服务：

```bash
docker compose restart
```

获取新代码并重新构建：

```bash
git pull
docker compose up -d --build
```

不要随意执行 `docker compose down -v`：`-v` 会删除 PostgreSQL 数据卷，已导入的数据将丢失。

## Codex / AI Agent 接入

仓库包含 `.codex/config.toml` 和 `.agents/skills/analyze-personal-health/SKILL.md`。在仓库根目录启动 Codex 后，项目级 MCP 配置会通过以下命令启动只读服务：

```bash
docker compose run --rm -T -q mcp
```

可用工具仅包含健康概览、单指标趋势、无路线运动摘要、恢复上下文、数据质量、已生成报告和用户主动填写的目标。工具不提供任意 SQL、原始上传、GPS、ECG、生殖健康或病历访问。

示例提问：

- “分析我过去七天的恢复情况，先说明数据覆盖率。”
- “为什么这周静息心率比个人基线高？”
- “结合最近一个月的睡眠和运动，下周如何安排活动？”

MCP 在本地运行不等于模型推理一定在本地完成；聚合结果可能进入所用模型的上下文。因此默认只提供必要的汇总数据。如果未来需要跨机器 MCP，应使用 HTTPS/Tailscale 和独立 Bearer Token，不应暴露无认证 HTTP 服务。

## 常见问题

### 打不开 `http://localhost:8501`

1. 运行 `docker compose ps` 确认 `app` 正在运行。
2. 运行 `docker compose logs app` 查看错误。
3. 确认 8501 端口没有被其他程序占用。

### 数据库启动失败

运行 `docker compose logs db` 检查密码、磁盘空间和数据库初始化日志。如果数据库已经初始化，之后只修改 `.env` 中的用户名或密码不会自动修改现有 PostgreSQL 账号。

### Apple Health 文件上传或解析失败

- 确认上传的是「健康」App 直接生成的 `export.zip`，而不是解压后的 `export.xml`。
- 大文件需要更长时间和更多内存，处理期间不要重复点击导入按钮。
- 同时运行 `docker compose logs -f app` 可查看服务端错误。

## 已知限制 / 后续工作

- **小米运动健康解析器是"尽力而为"实现**：小米没有公开文档化的个人数据导出格式，`app/parsers/xiaomi.py` 用宽松的列名匹配来适配常见的 CSV/JSON 字段（date/time/timestamp、steps、heart_rate、weight 等）。如果你的导出文件解析不理想，把文件样本发给维护者，只需要调整对应的 `_parse_*` 函数，不需要改动整体结构。
- **睡眠阶段**：Apple 导出能区分 core/deep/rem/awake 等阶段；小米数据格式未知，目前统一按 `asleep` 处理，拿到真实样本后可以精化。
- 建议只基于个人 28 天基线；某指标至少有 14 个有效日后才参与趋势判断。
- 第一版不发送邮件、短信或第三方推送，也不让 Agent 修改健康数据或自动执行训练计划。
- 规则和 Agent 输出均为一般信息，不用于疾病诊断、治疗或替代专业医疗建议。

## 验证过的行为（本地用合成数据测试）

- `export.xml` 流式解析：步数、心率、静息心率、活动能量、体重、睡眠阶段均正确解析；`Workout` 元素同时兼容新旧两种导出格式（属性直挂 vs iOS 17+ 的 `WorkoutStatistics` 子元素）。
- 幂等性：同一份 `export.zip` 重复上传，第二次写入 0 条新记录。
- 小米 CSV 适配层：按列名模糊匹配正确识别出 steps / heart_rate。
