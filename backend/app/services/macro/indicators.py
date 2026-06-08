"""宏观指标静态注册表。

指标的元信息（名称、分类、FRED series、单位、判断规则、阈值与一句话理由）全部在代码里维护，
数据库只存观测值（见 ``MacroObservation``）。判断为确定性规则，不依赖外部模型。
"""

from dataclasses import dataclass
from typing import Literal

Judgment = Literal["bullish", "neutral", "bearish"]
Zone = Literal["high", "normal", "low"]
Category = Literal["rates", "inflation", "growth", "employment", "liquidity", "risk"]


@dataclass(frozen=True)
class MacroIndicator:
    key: str
    category: Category
    name: str
    name_en: str
    series_id: str  # FRED series id
    units: str  # FRED units 变换：lin 原值 / pc1 同比百分比
    unit_label: str  # 展示单位，如 "%"、"千人"、"十亿美元"
    decimals: int  # 展示小数位
    source: str
    explanation: str  # 基本解释（这是什么指标）
    good_when: Literal["up", "down"]  # 哪个方向对风险资产偏多
    neutral_band: float  # 中性带阈值
    band_type: Literal["abs", "rel"]  # abs 绝对变化 / rel 相对变化
    reason_bullish: str
    reason_bearish: str
    reason_neutral: str
    # 预警阈值与极端位置说明（部分水平类指标无阈值，留空）
    high: float | None = None
    low: float | None = None
    high_note: str = ""
    low_note: str = ""
    # 预测/前瞻（如有，附来源；部分指标无前瞻数据）
    forecast: float | None = None
    forecast_label: str | None = None
    forecast_source: str | None = None

    def judge(self, latest: float, previous: float) -> Judgment:
        change = latest - previous
        if self.band_type == "abs":
            threshold = self.neutral_band
        else:
            threshold = abs(previous) * self.neutral_band
        if abs(change) <= threshold:
            return "neutral"
        rising = change > 0
        if self.good_when == "up":
            return "bullish" if rising else "bearish"
        return "bearish" if rising else "bullish"

    def zone(self, latest: float) -> Zone:
        if self.high is not None and latest >= self.high:
            return "high"
        if self.low is not None and latest <= self.low:
            return "low"
        return "normal"

    def reason(self, judgment: Judgment) -> str:
        if judgment == "bullish":
            return self.reason_bullish
        if judgment == "bearish":
            return self.reason_bearish
        return self.reason_neutral


INDICATORS: tuple[MacroIndicator, ...] = (
    # —— 利率与政策 ——
    MacroIndicator(
        key="fed_funds_rate",
        category="rates",
        name="联邦基金利率",
        name_en="Federal Funds Rate",
        series_id="FEDFUNDS",
        units="lin",
        unit_label="%",
        decimals=2,
        source="FRED",
        explanation="美联储政策利率，决定全市场无风险资金成本，是估值与流动性的总开关。",
        good_when="down",
        neutral_band=0.05,
        band_type="abs",
        reason_bullish="政策利率回落，融资成本下降、贴现率走低，利好风险资产估值。",
        reason_bearish="政策利率抬升，融资成本与贴现率上行，压制估值，对风险资产偏空。",
        reason_neutral="政策利率基本持平，货币政策面影响中性。",
        high=5.0,
        low=1.0,
        high_note="利率处于高位（≥5%）：融资成本高企、流动性偏紧，压制估值与经济活动。",
        low_note="利率处于低位（≤1%）：流动性极度宽松，利好风险资产，但通常对应经济疲弱或危机应对。",
        forecast=3.50,
        forecast_label="年内政策利率预期（参考，以实时概率为准）",
        forecast_source="CME FedWatch",
    ),
    MacroIndicator(
        key="treasury_10y",
        category="rates",
        name="10年期美债收益率",
        name_en="10-Year Treasury Yield",
        series_id="DGS10",
        units="lin",
        unit_label="%",
        decimals=2,
        source="FRED",
        explanation="长端无风险利率，是股票估值贴现的锚，也反映市场对增长与通胀的预期。",
        good_when="down",
        neutral_band=0.05,
        band_type="abs",
        reason_bullish="长端利率下行，贴现率走低，利好成长股与高估值板块。",
        reason_bearish="长端利率上行，抬高贴现率，压制成长股估值，对风险资产偏空。",
        reason_neutral="长端利率窄幅波动，对估值影响中性。",
        high=4.5,
        low=2.0,
        high_note="长端利率高位（≥4.5%）：贴现率高、估值承压，成长股尤其敏感。",
        low_note="长端利率低位（≤2%）：利于估值，但常伴随避险与衰退预期。",
    ),
    # —— 通胀 ——
    MacroIndicator(
        key="cpi_yoy",
        category="inflation",
        name="CPI 同比",
        name_en="CPI YoY",
        series_id="CPIAUCSL",
        units="pc1",
        unit_label="%",
        decimals=1,
        source="FRED",
        explanation="居民消费价格同比涨幅，衡量整体通胀，是美联储加减息的核心依据。",
        good_when="down",
        neutral_band=0.1,
        band_type="abs",
        reason_bullish="通胀回落，强化降息预期，利好风险资产。",
        reason_bearish="通胀回升，制约宽松空间、施压利率，对风险资产偏空。",
        reason_neutral="通胀基本持平，政策预期影响中性。",
        high=4.0,
        low=1.0,
        high_note="通胀高位（≥4%）：紧缩压力大，制约宽松、施压风险资产。",
        low_note="通胀低位（≤1%）：需求疲弱甚至通缩风险，但为降息打开空间。",
    ),
    MacroIndicator(
        key="core_pce_yoy",
        category="inflation",
        name="核心 PCE 同比",
        name_en="Core PCE YoY",
        series_id="PCEPILFE",
        units="pc1",
        unit_label="%",
        decimals=1,
        source="FRED",
        explanation="剔除食品能源的个人消费支出价格同比，是美联储最看重的通胀指标。",
        good_when="down",
        neutral_band=0.1,
        band_type="abs",
        reason_bullish="核心通胀降温，向 2% 目标靠拢，利好降息路径与风险资产。",
        reason_bearish="核心通胀粘性回升，延后宽松，对风险资产偏空。",
        reason_neutral="核心通胀基本持平，政策路径影响中性。",
        high=3.0,
        low=1.5,
        high_note="核心通胀高位（≥3%）：高于 2% 目标，宽松受限。",
        low_note="核心通胀低位（≤1.5%）：接近或低于目标，利于降息。",
    ),
    # —— 增长 ——
    MacroIndicator(
        key="real_gdp_growth",
        category="growth",
        name="实际 GDP 环比年化",
        name_en="Real GDP Growth (QoQ Ann.)",
        series_id="A191RL1Q225SBEA",
        units="lin",
        unit_label="%",
        decimals=1,
        source="FRED",
        explanation="实际经济产出的环比年化增速，衡量经济扩张或收缩的力度。",
        good_when="up",
        neutral_band=0.3,
        band_type="abs",
        reason_bullish="经济增速加快，盈利预期改善，利好风险资产。",
        reason_bearish="经济增速放缓，盈利承压，对风险资产偏空。",
        reason_neutral="增速基本平稳，经济面影响中性。",
        high=3.0,
        low=0.0,
        high_note="增长强劲（≥3%）：盈利向好，但也可能引发过热与紧缩担忧。",
        low_note="增长停滞或收缩（≤0%）：衰退风险高，盈利承压。",
    ),
    # —— 就业 ——
    MacroIndicator(
        key="unemployment_rate",
        category="employment",
        name="失业率",
        name_en="Unemployment Rate",
        series_id="UNRATE",
        units="lin",
        unit_label="%",
        decimals=1,
        source="FRED",
        explanation="劳动力市场松紧的核心指标，过低易推升工资通胀，过高预示衰退风险。",
        good_when="down",
        neutral_band=0.1,
        band_type="abs",
        reason_bullish="失业率下行，劳动力市场稳健，支撑消费与盈利。",
        reason_bearish="失业率上行，就业走弱，提升衰退担忧，对风险资产偏空。",
        reason_neutral="失业率基本持平，就业面影响中性。",
        high=5.0,
        low=3.5,
        high_note="失业率高位（≥5%）：经济走弱、消费承压，衰退信号。",
        low_note="失业率低位（≤3.5%）：劳动力市场过热，易推升工资通胀。",
    ),
    MacroIndicator(
        key="nonfarm_payrolls",
        category="employment",
        name="非农就业人数",
        name_en="Nonfarm Payrolls",
        series_id="PAYEMS",
        units="lin",
        unit_label="千人",
        decimals=0,
        source="FRED",
        explanation="非农部门就业总人数，其月度变化即新增非农就业，直接反映经济动能。",
        good_when="up",
        neutral_band=50.0,
        band_type="abs",
        reason_bullish="新增就业强劲，经济动能充足，利好风险资产。",
        reason_bearish="就业增长转弱甚至萎缩，经济动能下滑，对风险资产偏空。",
        reason_neutral="就业增长平稳，经济动能影响中性。",
    ),
    # —— 流动性 ——
    MacroIndicator(
        key="m2_money_supply",
        category="liquidity",
        name="M2 货币供应",
        name_en="M2 Money Supply",
        series_id="M2SL",
        units="lin",
        unit_label="十亿美元",
        decimals=0,
        source="FRED",
        explanation="广义货币供应量，反映金融体系整体流动性的扩张或收缩。",
        good_when="up",
        neutral_band=0.002,
        band_type="rel",
        reason_bullish="货币供应扩张，流动性充裕，利好风险资产。",
        reason_bearish="货币供应收缩，流动性趋紧，对风险资产偏空。",
        reason_neutral="货币供应基本平稳，流动性影响中性。",
    ),
    MacroIndicator(
        key="yield_spread_10y2y",
        category="liquidity",
        name="2s10s 利差",
        name_en="10Y-2Y Yield Spread",
        series_id="T10Y2Y",
        units="lin",
        unit_label="%",
        decimals=2,
        source="FRED",
        explanation="10年与2年美债收益率之差，倒挂（负值）常被视为衰退领先信号。",
        good_when="up",
        neutral_band=0.05,
        band_type="abs",
        reason_bullish="收益率曲线走陡，衰退信号缓和，利好风险资产。",
        reason_bearish="收益率曲线趋平/倒挂加深，衰退担忧升温，对风险资产偏空。",
        reason_neutral="曲线形态基本稳定，影响中性。",
        high=1.5,
        low=0.0,
        high_note="曲线陡峭（≥1.5%）：通常对应复苏早期，利好顺周期资产。",
        low_note="曲线倒挂（≤0%）：历史上领先衰退 12-18 个月，风险偏空。",
    ),
    # —— 风险 ——
    MacroIndicator(
        key="vix",
        category="risk",
        name="VIX 波动率",
        name_en="VIX Volatility Index",
        series_id="VIXCLS",
        units="lin",
        unit_label="",
        decimals=2,
        source="FRED",
        explanation="标普500隐含波动率，俗称恐慌指数，衡量市场避险情绪与不确定性。",
        good_when="down",
        neutral_band=0.05,
        band_type="rel",
        reason_bullish="波动率回落，避险情绪降温，风险偏好回升。",
        reason_bearish="波动率走高，避险情绪升温，对风险资产偏空。",
        reason_neutral="波动率基本平稳，市场情绪影响中性。",
        high=30.0,
        low=13.0,
        high_note="恐慌指数高位（≥30）：市场剧烈避险，往往对应阶段性底部区域。",
        low_note="波动率低位（≤13）：情绪乐观甚至自满，警惕反转风险。",
    ),
    MacroIndicator(
        key="hy_spread",
        category="risk",
        name="高收益债利差",
        name_en="High Yield Spread",
        series_id="BAMLH0A0HYM2",
        units="lin",
        unit_label="%",
        decimals=2,
        source="FRED",
        explanation="高收益债相对国债的利差，反映信用风险定价，走阔预示融资环境收紧。",
        good_when="down",
        neutral_band=0.1,
        band_type="abs",
        reason_bullish="信用利差收窄，融资环境改善，利好风险资产。",
        reason_bearish="信用利差走阔，违约担忧升温、融资趋紧，对风险资产偏空。",
        reason_neutral="信用利差基本持平，信用面影响中性。",
        high=5.0,
        low=3.0,
        high_note="信用利差高位（≥5%）：融资环境紧张、违约担忧升温，风险偏空。",
        low_note="信用利差低位（≤3%）：风险偏好高、融资宽松。",
    ),
)

INDICATORS_BY_KEY: dict[str, MacroIndicator] = {ind.key: ind for ind in INDICATORS}


def get_indicator(key: str) -> MacroIndicator | None:
    return INDICATORS_BY_KEY.get(key)
