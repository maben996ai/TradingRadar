"""真实联调：对 AAPL 实跑一次 download_fundamentals，打印落盘清单。

用法（在 backend/ 下）：python scripts/verify_fundamentals.py [TICKER]
读取仓库根 .env 的真实 key；缺 key 的数据源会自动 skipped。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.fundamentals.service import download_fundamentals  # noqa: E402


async def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    outcomes = await download_fundamentals(ticker)
    for o in outcomes:
        head = f"[{o.source}]"
        if o.skipped:
            print(f"{head} SKIPPED: {o.message}")
            continue
        print(f"{head} {len(o.artifacts)} 个文件" + (f" | {o.message}" if o.message else ""))
        for a in o.artifacts:
            kb = a.bytes_written / 1024
            print(f"    - {a.doc_type:<22} {kb:8.1f} KB  {a.file_path}")


if __name__ == "__main__":
    asyncio.run(main())
