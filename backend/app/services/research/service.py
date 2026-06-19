"""标的研报检索：按公司代码在各信源中检索近 N 天的研报/行业分析与 SEC 披露。

接口按「单源」粒度设计，前端逐源调用即可展示检索进度：
- RSS 源：在已抓取的 content_items 中按 代码/公司名 匹配标题与正文；
- SEC EDGAR：实时列出该公司近 N 天的披露（10-K/10-Q/8-K 等），给原文链接。
"""

import logging
import re
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.models import ContentItem, SourceType
from app.services.research.rss_sources import RSS_BUILTIN_SOURCES

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 90
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
FMP_SEARCH_URL = "https://financialmodelingprep.com/stable/search-symbol"
REQUEST_TIMEOUT = 30.0
SEC_FORMS = ("10-K", "10-Q", "8-K", "S-1", "13F-HR", "DEF 14A", "20-F", "6-K")
SEC_SOURCE_KEY = "sec_edgar"

# 公司名中无信息量的法律后缀，剥离后得到用于匹配的简称
_NAME_SUFFIXES = {
    "inc", "corp", "corporation", "company", "co", "ltd", "plc", "sa", "nv", "ag",
    "holdings", "holding", "group", "lp", "llc", "incorporated", "limited", "the",
}


class TickerNotFound(ValueError):
    """各数据源均找不到该代码。"""


def list_sources() -> list[dict]:
    """检索源清单：全部 RSS 内置源 + SEC EDGAR。"""
    sources = [{"key": s["url"], "name": s["name"]} for s in RSS_BUILTIN_SOURCES]
    sources.append({"key": SEC_SOURCE_KEY, "name": "SEC EDGAR 监管披露"})
    return sources


def _short_name(full_name: str) -> str:
    """'NVIDIA CORP' → 'NVIDIA'；'Apple Inc.' → 'Apple'。"""
    cleaned = re.sub(r"[.,/\\]", " ", full_name)
    words = [w for w in cleaned.split() if w.lower() not in _NAME_SUFFIXES]
    return " ".join(words) if words else full_name.strip()


def _sec_user_agent() -> str:
    return get_settings().sec_edgar_user_agent or "TradingRadar research"


async def resolve_company_name(ticker: str) -> str:
    """优先 FMP（部分网络环境 sec.gov 不可达），回退 SEC 公司表。"""
    ticker = ticker.strip().upper()
    api_key = get_settings().fmp_api_key
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    FMP_SEARCH_URL, params={"query": ticker, "apikey": api_key}
                )
                resp.raise_for_status()
                for entry in resp.json():
                    if str(entry.get("symbol", "")).upper() == ticker:
                        return str(entry.get("name") or ticker)
        except httpx.HTTPError as exc:
            logger.warning("FMP 代码解析失败（%s）：%s", ticker, exc)

    try:
        cik, name = await _resolve_cik_and_name(ticker)
        if cik:
            return name
    except httpx.HTTPError as exc:
        logger.warning("SEC 公司表解析失败（%s）：%s", ticker, exc)
    raise TickerNotFound(f"未找到代码 {ticker} 对应的公司")


async def _resolve_cik_and_name(ticker: str) -> tuple[str | None, str]:
    """从 SEC 公司表解析 (cik 十位补零, 公司全名)；找不到返回 (None, ticker)。"""
    headers = {"User-Agent": _sec_user_agent(), "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers) as client:
        resp = await client.get(COMPANY_TICKERS_URL)
        resp.raise_for_status()
        for entry in resp.json().values():
            if str(entry.get("ticker", "")).upper() == ticker:
                return f"{int(entry['cik_str']):010d}", str(entry.get("title", ticker))
    return None, ticker


def _matches(title: str, body: str, ticker: str, short_name: str) -> bool:
    """代码符号精确命中即算；公司名需出现在标题、或正文中≥3次（过滤顺带提及的误报）。"""
    text = f"{title}\n{body}"
    if re.search(rf"\b{re.escape(ticker)}\b", text):
        return True
    name = short_name.lower()
    if name in title.lower():
        return True
    return body.lower().count(name) >= 3


async def search_source(db: AsyncSession, ticker: str, source_key: str) -> dict:
    """在单个源中检索；返回 {items, error}，源不可达时 error 给出说明而非抛错。"""
    ticker = ticker.strip().upper()
    company_name = await resolve_company_name(ticker)
    short_name = _short_name(company_name)
    window_start = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)

    if source_key == SEC_SOURCE_KEY:
        return await _search_sec(ticker, window_start.date())
    return await _search_rss_feed(db, source_key, ticker, short_name, window_start)


async def _search_rss_feed(
    db: AsyncSession, feed_url: str, ticker: str, short_name: str, window_start: datetime
) -> dict:
    rows = list(
        await db.scalars(
            select(ContentItem)
            .options(selectinload(ContentItem.data_source))
            .join(ContentItem.data_source)
            .where(
                ContentItem.data_source.has(source_type=SourceType.RSS),
                ContentItem.data_source.has(external_id=feed_url),
                ContentItem.published_at >= window_start,
            )
            .order_by(ContentItem.published_at.desc())
        )
    )
    items: list[dict] = []
    seen_urls: set[str] = set()
    for item in rows:
        if item.content_url in seen_urls:
            continue
        raw = item.raw_data or {}
        body = raw.get("text") if isinstance(raw, dict) else ""
        if not _matches(item.title, body if isinstance(body, str) else "", ticker, short_name):
            continue
        seen_urls.add(item.content_url)
        items.append(
            {
                "title": item.title,
                "url": item.content_url,
                "meta": item.published_at.date().isoformat(),
                "published_at": item.published_at,
            }
        )
    return {"items": items, "error": None}


async def _search_sec(ticker: str, window_start: date) -> dict:
    try:
        cik, _ = await _resolve_cik_and_name(ticker)
        if cik is None:
            return {"items": [], "error": f"SEC 公司表中无代码 {ticker}"}
        filings = await _list_sec_filings(cik, window_start)
    except httpx.HTTPError as exc:
        logger.warning("SEC 披露获取失败（%s）：%s", ticker, exc)
        return {"items": [], "error": "SEC EDGAR 暂不可达（当前网络环境可能被拦截）"}
    items = [
        {
            "title": f"{f['form']}" + (f" · {f['description']}" if f["description"] else ""),
            "url": f["url"],
            "meta": f["filing_date"].isoformat(),
            "published_at": None,
        }
        for f in filings
    ]
    return {"items": items, "error": None}


async def _list_sec_filings(cik: str, window_start: date) -> list[dict]:
    headers = {"User-Agent": _sec_user_agent(), "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers) as client:
        resp = await client.get(SUBMISSIONS_URL.format(cik=cik))
        resp.raise_for_status()
        recent = resp.json().get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])
    descriptions = recent.get("primaryDocDescription", [])

    target = set(SEC_FORMS)
    filings: list[dict] = []
    for i, form in enumerate(forms):
        if form not in target:
            continue
        try:
            filing_date = date.fromisoformat(filing_dates[i] if i < len(filing_dates) else "")
        except ValueError:
            continue
        if filing_date < window_start:
            continue
        document = documents[i] if i < len(documents) else ""
        accession = accessions[i] if i < len(accessions) else ""
        url = (
            ARCHIVE_URL.format(
                cik=int(cik), accession=accession.replace("-", ""), document=document
            )
            if document and accession
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
        )
        filings.append(
            {
                "form": form,
                "filing_date": filing_date,
                "description": descriptions[i] if i < len(descriptions) else "",
                "url": url,
            }
        )
    return filings
