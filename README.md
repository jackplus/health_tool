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

## 快速开始

```bash
cp .env.example .env   # 按需修改密码
docker compose up -d --build
```

浏览器打开 `http://<你的服务器>:8501`，先去 **Upload** 页面上传一份 Apple Health `export.zip`。

## 已知限制 / 后续工作

- **小米运动健康解析器是"尽力而为"实现**：小米没有公开文档化的个人数据导出格式，`app/parsers/xiaomi.py` 用宽松的列名匹配来适配常见的 CSV/JSON 字段（date/time/timestamp、steps、heart_rate、weight 等）。如果你的导出文件解析不理想，把文件样本发给维护者，只需要调整对应的 `_parse_*` 函数，不需要改动整体结构。
- **睡眠阶段**：Apple 导出能区分 core/deep/rem/awake 等阶段；小米数据格式未知，目前统一按 `asleep` 处理，拿到真实样本后可以精化。
- **v1 没有自动定时任务**：看板直接查询原始数据（有索引，个人数据量级下足够快）。如果以后数据量变大导致变慢，可以在 Settings 页面手动触发 `daily_rollups` 汇总重算，或者启用 `app/scheduler.py` 里预留的 APScheduler 夜间自动重算（默认未开启）。

## 验证过的行为（本地用合成数据测试）

- `export.xml` 流式解析：步数、心率、静息心率、活动能量、体重、睡眠阶段均正确解析；`Workout` 元素同时兼容新旧两种导出格式（属性直挂 vs iOS 17+ 的 `WorkoutStatistics` 子元素）。
- 幂等性：同一份 `export.zip` 重复上传，第二次写入 0 条新记录。
- 小米 CSV 适配层：按列名模糊匹配正确识别出 steps / heart_rate。
