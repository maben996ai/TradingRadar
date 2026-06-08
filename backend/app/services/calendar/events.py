"""财经日历的精选事件定义与默认财报公司。

事件元信息（分类/标题/重要性/影响资产/发布节奏/FRED 回填 series）在代码维护，
数据库只存生成后的事件实例（见 ``CalendarEvent``）。
"""

from dataclasses import dataclass
from typing import Literal

ScheduleKind = Literal["nth_weekday", "dom", "weekly", "quarterly_dom", "explicit"]


@dataclass(frozen=True)
class MacroEventDef:
    key: str
    category: Literal["inflation", "employment", "rates", "growth"]
    title: str
    title_en: str
    importance: int  # 1 低 / 2 中 / 3 高
    impact_assets: str
    value_unit: str
    fred_series: str | None  # 回填 actual/previous 的 FRED series（无则留空）
    fred_units: str  # lin 原值 / pc1 同比
    schedule_kind: ScheduleKind
    schedule_arg: int  # nth_weekday→weekday；dom/quarterly_dom→日；weekly→weekday
    schedule_nth: int  # nth_weekday→第几个
    hour_et: int
    minute_et: int


# FOMC 2026 利率决议日（议息第二天，待校准）；季度会议附经济预测/点阵图
FOMC_DECISION_DATES_2026 = [
    (1, 28), (3, 18), (4, 29), (6, 17), (7, 29), (9, 16), (10, 28), (12, 9),
]
FOMC_PROJECTION_DATES_2026 = [(3, 18), (6, 17), (9, 16), (12, 9)]


MACRO_EVENTS: tuple[MacroEventDef, ...] = (
    # —— 通胀 ——
    MacroEventDef("cpi", "inflation", "CPI 同比", "CPI YoY", 3, "美元、美股、黄金", "%",
                  "CPIAUCSL", "pc1", "dom", 12, 0, 8, 30),
    MacroEventDef("core_cpi", "inflation", "核心 CPI 同比", "Core CPI YoY", 3, "美元、美股", "%",
                  "CPILFESL", "pc1", "dom", 12, 0, 8, 30),
    MacroEventDef("ppi", "inflation", "PPI 同比", "PPI YoY", 2, "美元、美债", "%",
                  "PPIACO", "pc1", "dom", 13, 0, 8, 30),
    MacroEventDef("pce", "inflation", "PCE 同比", "PCE YoY", 3, "美元、美股、黄金", "%",
                  "PCEPI", "pc1", "dom", 28, 0, 8, 30),
    MacroEventDef("core_pce", "inflation", "核心 PCE 同比", "Core PCE YoY", 3, "美元、美股", "%",
                  "PCEPILFE", "pc1", "dom", 28, 0, 8, 30),
    # —— 就业 ——
    MacroEventDef("nfp", "employment", "非农就业人数", "Nonfarm Payrolls", 3, "美元、美股、黄金", "千人",
                  "PAYEMS", "chg", "nth_weekday", 4, 1, 8, 30),
    MacroEventDef("unemployment", "employment", "失业率", "Unemployment Rate", 3, "美元、美股", "%",
                  "UNRATE", "lin", "nth_weekday", 4, 1, 8, 30),
    MacroEventDef("jobless_claims", "employment", "初请失业金人数", "Initial Jobless Claims", 2,
                  "美元、美股", "千人", "ICSA", "lin", "weekly", 3, 0, 8, 30),
    MacroEventDef("jolts", "employment", "JOLTS 职位空缺", "JOLTS Job Openings", 2, "美元、美股", "千人",
                  "JTSJOL", "lin", "dom", 4, 0, 10, 0),
    # —— 利率 ——
    MacroEventDef("fomc_decision", "rates", "FOMC 利率决议", "FOMC Rate Decision", 3,
                  "美元、美股、美债、黄金", "%", "DFEDTARU", "lin", "explicit", 0, 0, 14, 0),
    MacroEventDef("fomc_presser", "rates", "鲍威尔新闻发布会", "Powell Press Conference", 3,
                  "美元、美股、美债", "", None, "lin", "explicit", 0, 0, 14, 30),
    MacroEventDef("fomc_dots", "rates", "经济预测与点阵图", "Dot Plot & Projections", 2,
                  "美元、美股、美债", "", None, "lin", "explicit", 0, 0, 14, 0),
    MacroEventDef("fomc_minutes", "rates", "FOMC 会议纪要", "FOMC Minutes", 2, "美元、美债", "",
                  None, "lin", "explicit", 0, 0, 14, 0),
    # —— 增长 ——
    MacroEventDef("gdp", "growth", "GDP 环比年化", "GDP QoQ Ann.", 3, "美元、美股", "%",
                  "A191RL1Q225SBEA", "lin", "quarterly_dom", 30, 0, 8, 30),
    MacroEventDef("ism_mfg", "growth", "ISM 制造业 PMI", "ISM Manufacturing PMI", 3, "美元、美股", "",
                  None, "lin", "dom", 1, 0, 10, 0),
    MacroEventDef("ism_services", "growth", "ISM 服务业 PMI", "ISM Services PMI", 3, "美元、美股", "",
                  None, "lin", "dom", 3, 0, 10, 0),
    MacroEventDef("retail_sales", "growth", "零售销售同比", "Retail Sales YoY", 3, "美元、美股", "%",
                  "RSAFS", "pc1", "dom", 15, 0, 8, 30),
)

MACRO_EVENTS_BY_KEY = {e.key: e for e in MACRO_EVENTS}


# 默认重点公司（纳指100/标普500 核心），用户可在前端再添加关注代码
@dataclass(frozen=True)
class CompanyDef:
    ticker: str
    name: str
    importance: int


DEFAULT_COMPANIES: tuple[CompanyDef, ...] = (
    CompanyDef("AAPL", "苹果", 3),
    CompanyDef("MSFT", "微软", 3),
    CompanyDef("NVDA", "英伟达", 3),
    CompanyDef("AMZN", "亚马逊", 3),
    CompanyDef("GOOGL", "谷歌", 3),
    CompanyDef("META", "Meta", 3),
    CompanyDef("TSLA", "特斯拉", 3),
    CompanyDef("AVGO", "博通", 2),
    CompanyDef("JPM", "摩根大通", 2),
    CompanyDef("NFLX", "奈飞", 2),
)
