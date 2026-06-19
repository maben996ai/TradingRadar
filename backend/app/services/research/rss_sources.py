"""预置研报/行业分析 RSS 信源（全局内置，按用户 provision，external_id 即订阅源 URL）。

均为实测可解析的公开 feed。BIS/IMF/OECD/世界银行/BOE/Man Institute 的公开 RSS
当前被源站拦截（403/404/SSL），待找到可用地址后补充。
"""

RSS_BUILTIN_SOURCES: tuple[dict[str, str], ...] = (
    # —— 官方机构 · 宏观 ——
    {"url": "https://www.federalreserve.gov/feeds/press_all.xml", "name": "美联储新闻稿"},
    {"url": "https://fredblog.stlouisfed.org/feed/", "name": "FRED Blog（圣路易斯联储）"},
    {
        "url": "https://libertystreeteconomics.newyorkfed.org/feed/",
        "name": "Liberty Street（纽约联储）",
    },
    {"url": "https://www.ecb.europa.eu/rss/press.html", "name": "ECB 欧央行新闻"},
    {"url": "https://www.ecb.europa.eu/rss/pub.html", "name": "ECB 欧央行研究出版物"},
    {"url": "https://www.boj.or.jp/en/rss/whatsnew.xml", "name": "BOJ 日本央行"},
    # —— 独立研究者 · Substack ——
    {
        "url": "https://aswathdamodaran.blogspot.com/feeds/posts/default?alt=rss",
        "name": "Aswath Damodaran（估值）",
    },
    {"url": "https://www.netinterest.co/feed", "name": "Net Interest（金融业）"},
    {"url": "https://thetranscript.substack.com/feed", "name": "The Transcript（财报电话会）"},
    {"url": "https://doomberg.substack.com/feed", "name": "Doomberg（能源与大宗）"},
    {"url": "https://www.apricitas.io/feed", "name": "Apricitas Economics（美国宏观）"},
)
