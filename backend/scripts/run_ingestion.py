#!/usr/bin/env python3
from __future__ import annotations

import sys

def main() -> None:
    print(
        "run_ingestion.py 已禁用：项目已移除传统爬虫（requests/BeautifulSoup）。\n"
        "请改用 MCP+浏览器自动化流程：\n"
        "1) python scripts/xhs_ai_extract_to_table.py ...\n"
        "2) 或 python scripts/run_top30_source_queries.py ...",
        file=sys.stderr,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
