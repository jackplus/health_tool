# 个人运动健康数据中心

自托管的个人运动健康数据 BI 看板：整合 Apple Health 与小米运动健康的数据，用 Streamlit 呈现趋势和关键指标。

## 为什么是手动上传

Apple Health（HealthKit）和小米运动健康都**没有面向个人开发者的官方云端拉取 API**。因此本项目不做定时轮询，而是：

1. 你定期在手机 App 里手动导出数据（Apple「健康」App 导出 `export.zip`；小米运动健康 App 申请个人数据导出得到 CSV/JSON）。
2. 在本系统的 **Upload** 页面上传这些文件。
3. 系统解析、去重、写入数据库，看板自动更新。

重复上传同一份 Apple 全量导出是安全的——已存在的记录会被自动跳过（基于唯一约束的幂等写入），不会产生重复数据。

## 架构

- `db`：PostgreSQL，存储归一化后的健康指标（`health_metrics`）、运动记录（`workouts`）和上传审计记录（`raw_uploads`）。
- `app`：Python 3.12 + Streamlit，既是看板也是上传入口（`st.file_uploader`）。

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
      xiaomi.py             # 小米导出的尽力而为适配层
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

打开 `.env`，至少把默认数据库密码 `change_me` 改成一个强密码：

```dotenv
POSTGRES_USER=health
POSTGRES_PASSWORD=请替换为强密码
POSTGRES_DB=health
POSTGRES_HOST=db
POSTGRES_PORT=5432
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

正常情况下，`db` 应显示为 `healthy`，`app` 应显示为运行中。如果启动失败，查看日志：

```bash
docker compose logs -f app
docker compose logs -f db
```

按 `Ctrl+C` 可退出日志查看，不会停止服务。

### 5. 打开看板

本机运行时，在浏览器打开：

```text
http://localhost:8501
```

如果 Docker 运行在另一台服务器上，将 `localhost` 替换为服务器 IP 或域名。健康数据属于敏感信息，请不要将 8501 端口直接暴露到公网；远程部署时应使用 HTTPS 和身份认证。

## 上传健康数据

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
- **v1 没有自动定时任务**：看板直接查询原始数据（有索引，个人数据量级下足够快）。如果以后数据量变大导致变慢，可以在 Settings 页面手动触发 `daily_rollups` 汇总重算，或者启用 `app/scheduler.py` 里预留的 APScheduler 夜间自动重算（默认未开启）。

## 验证过的行为（本地用合成数据测试）

- `export.xml` 流式解析：步数、心率、静息心率、活动能量、体重、睡眠阶段均正确解析；`Workout` 元素同时兼容新旧两种导出格式（属性直挂 vs iOS 17+ 的 `WorkoutStatistics` 子元素）。
- 幂等性：同一份 `export.zip` 重复上传，第二次写入 0 条新记录。
- 小米 CSV 适配层：按列名模糊匹配正确识别出 steps / heart_rate。
