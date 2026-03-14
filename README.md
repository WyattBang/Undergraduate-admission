# 美本申请预测 MVP

本项目实现了一个面向中国留学生申请美本名校的 MVP：
- 公开社媒数据采集（仅 MCP+浏览器自动化）
- 数据标准化与训练集构建（`raw -> normalized -> training_set`）
- 录取概率模型（GBDT/CatBoost + Platt/Isotonic 校准）
- FastAPI 预测接口
- React 可视化页面（表单输入 -> 概率 + 短板诊断 + 冲稳保建议）

## 架构

- `backend/`
  - `app/ingestion`: 字段抽取、匿名化、去重
  - `app/pipeline`: 标准化、训练集、训练与校准
  - `app/services`: 特征工程、预测、解释、推荐
  - `app/api`: `predict/schools/majors/health` 接口
- `frontend/`
  - React + Vite 单页应用

## 合规边界（MVP）

- 仅采集公开可见页面。
- 不采集登录态内容。
- 匿名化处理：去除用户标识、URL、联系方式等 PII。
- 仅保留建模所需结构化字段。

## 快速开始

### 1) 后端

```bash
cd /Users/wyatt/Codex/留学生申请预测/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 生成演示数据并训练模型

```bash
python scripts/seed_demo_data.py
python -m app.pipeline.training_set
python scripts/train_model.py
```

如果你有真实抓取到的 raw 批次（`backend/data/raw/*.jsonl`），则跑：

```bash
python scripts/run_pipeline.py
```

批量导入人工整理案例（推荐，稳定扩充数据）：

```bash
python scripts/import_cases_csv.py --csv data/templates/manual_cases_template.csv
```

说明：`scripts/run_ingestion.py` 已禁用（传统爬虫已移除），仅保留 MCP+浏览器自动化采集链路。

抽检标签质量并在不达标时回滚批次：

```bash
python scripts/audit_batch.py --normalized-file data/normalized/xxx.jsonl --audit-csv /path/to/audit.csv --threshold 0.85
```

查看数据覆盖缺口（知道该优先补哪些学校/专业）：

```bash
python scripts/data_gap_report.py --min-samples 80 --top 20
```

使用多模态 AI 抽取帖子图片与正文信息（推荐替代纯 OCR）：

```bash
export OPENAI_API_KEY=your_key
python scripts/xhs_ai_extract_to_table.py --keyword "留学 美本 申请" --limit 12 --model gpt-4.1-mini
```

按 `Top30名校 + 录取背景 + 美本` 的 source query 批量抓取并自动汇总（推荐）：

```bash
python scripts/run_top30_source_queries.py \
  --top-n 30 \
  --limit-per-query 6 \
  --max-images-per-post 1 \
  --model gpt-4.1-mini
```

该命令会输出：
- `data/raw/xhs_top30_<query>_raw.jsonl`
- `data/normalized/xhs_top30_<query>_cleaned.jsonl/.csv`
- `data/normalized/xhs_top30_merged_cleaned.jsonl/.csv`
- `data/normalized/xhs_top30_run_manifest.json`

大规模抓取建议（关键词扩展 + 多过滤去重池）：

```bash
python scripts/xhs_ai_extract_to_table.py \
  --keyword "美本申请bg" \
  --target-raw 1200 \
  --limit 400 \
  --max-images-per-post 2 \
  --model gpt-4.1-mini
```

输出文件：
- `data/raw/xhs_<keyword>_ai_raw.jsonl`（原始抽取结果）
- `data/normalized/xhs_<keyword>_ai_cleaned.jsonl`
- `data/normalized/xhs_<keyword>_ai_cleaned.csv`

若先验证流程不调用模型：

```bash
python scripts/xhs_ai_extract_to_table.py --keyword "留学 美本 申请" --limit 5 --dry-run
```

清理历史临时文件并归档（保持目录整洁）：

```bash
# 先预览
python scripts/cleanup_xhs_outputs.py

# 再执行归档
python scripts/cleanup_xhs_outputs.py --execute
```

### 3) 启动 API

```bash
uvicorn app.main:app --reload --port 8000
```

接口：
- `GET /api/v1/health`
- `GET /api/v1/schools`
- `GET /api/v1/majors`
- `POST /api/v1/predict`

### 4) 启动前端

```bash
cd /Users/wyatt/Codex/留学生申请预测/frontend
npm install
npm run dev
```

默认访问 [http://localhost:5173](http://localhost:5173)

## 主要 API 契约

### `POST /api/v1/predict`

请求字段：
- `target_school`, `target_major`
- `english_test_type`, `english_score`
- `curriculum_type`, `gpa`, `course_scores[]`
- `activities[]`, `awards[]`, `research[]`
- `grad_year`

响应字段：
- `admit_probability`
- `confidence_band`
- `top_factors[]`
- `weakness_diagnosis[]`
- `reach_match_safe_schools[]`
- `model_version`, `data_cutoff_date`

## 测试

```bash
cd /Users/wyatt/Codex/留学生申请预测/backend
pytest
```

## PostgreSQL

启动数据库：

```bash
docker compose up -d postgres
```

然后把 `DATABASE_URL` 设为：

```text
postgresql+psycopg2://postgres:postgres@localhost:5432/admit_predictor
```

> 开发环境默认回退到 SQLite，生产建议使用 PostgreSQL。
