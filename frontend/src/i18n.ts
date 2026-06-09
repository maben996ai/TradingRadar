import { computed, ref, watch } from "vue";

export type Locale = "zh-CN" | "en";

const LOCALE_KEY = "trendradar_locale";
const defaultLocale: Locale = "zh-CN";

const messages = {
  "zh-CN": {
    app: {
      localeLabel: "语言",
      switchToChinese: "切换到中文",
      switchToEnglish: "Switch to English",
    },
    nav: {
      dataSources: "信源管理",
      controlCenter: "控制中心",
      contentAnalysis: "投研分析",
      signOut: "退出登录",
      searchPlaceholder: "搜索信源、关键词…",
      sectionSources: "信源",
      sectionAnalysis: "分析",
      socialMedia: "社交媒体",
      financeVideo: "财经视频",
      financeNews: "金融时讯",
      macroMarket: "市场宏观",
      financeCalendar: "财经日历",
      srcJin10: "金十数据",
      srcYahoo: "雅虎财经",
      srcBloomberg: "彭博",
      srcReuters: "路透社",
      macroRates: "利率与政策",
      macroInflation: "通胀",
      macroGrowth: "经济增长",
      macroEmployment: "就业",
      macroLiquidity: "流动性",
      macroRisk: "风险偏好",
      calCentralBank: "央行政策",
      calIndustry: "行业事件",
      calEarnings: "公司财报",
      stockAnalysis: "个股分析",
      marketAnalysis: "市场分析",
      memberOnline: "Pro 会员 · 在线",
    },
    feed: {
      eyebrow: "内容动态",
      title: "最新动态",
      sortByTime: "按时间",
      sortByAuthor: "按作者",
      loading: "加载中…",
      empty: "暂无视频，先去添加信源并触发抓取吧。",
      fetchError: "加载失败，请稍后重试。",
      prevPage: "上一页",
      nextPage: "下一页",
      tabVideos: "视频",
      tabArticles: "文章",
      tabNews: "资讯",
      tabMarket: "市场",
      viewAll: "查看全部",
      showMore: "显示更多",
      showLess: "收起",
      viewOriginal: "查看原文",
      comingSoon: "即将上线，敬请期待",
      backToFeed: "← 返回动态",
      itemsUnit: "条",
      refresh: "刷新",
      today: "今天",
      yesterday: "昨天",
      statTotal: "条内容",
      statSources: "个信源",
      placeholderHint: "该板块即将接入真实数据，当前为示例内容。",
      placeholderSummary: "后端数据源接入后，这里将展示来自金融时讯、宏观市场等渠道的实时内容。",
    },
    dataSources: {
      eyebrow: "信源",
      title: "信源管理",
      addPlaceholder: "粘贴 X 或 YouTube 作者主页链接",
      addButton: "添加",
      adding: "添加中…",
      empty: "还没有订阅的信源，粘贴主页链接开始添加。",
      loading: "加载中…",
      fetchError: "加载失败，请稍后重试。",
      addError: "添加失败，请检查链接格式或网络。",
      initializing: "初始化中…",
      deleteConfirm: "确认删除该信源？",
      notePlaceholder: "备注（可选）",
      categoryPlaceholder: "分类（可选）",
      contentTypeLabel: "内容类型",
      editTitle: "编辑信源",
      save: "保存",
      cancel: "取消",
      starred: "特别关注",
      unstar: "取消特别关注",
      edit: "编辑",
      delete: "删除",
      tabVideos: "视频",
      tabArticles: "文章",
      tabNews: "资讯",
      tabMarket: "市场",
      comingSoon: "该板块即将上线",
      platformYoutube: "YouTube",
      platformTwitter: "X",
      builtinFinanceNews: "金十数据为系统内置信源，每 10 分钟自动同步最新快讯。",
      platformWechat: "公众号",
      platformWebsite: "网站",
    },
    contentAnalysis: {
      eyebrow: "投研分析",
      title: "投研分析",
      description: "基于大模型的视频内容分析与投研洞察，即将上线。",
    },
    stockAnalysis: {
      eyebrow: "个股分析",
      title: "个股财报与披露下载",
      description: "输入美股代码，自动抓取并下载对应的财报、披露文件与分析师预期。",
      tickerPlaceholder: "公司代码，如 AAPL",
      sourcesLabel: "数据源：",
      downloadBtn: "开始下载",
      downloading: "下载中…",
      files: "个文件",
      skipped: "已跳过",
      colType: "类型",
      colTitle: "标题",
      colPeriod: "报告期",
      colSize: "大小",
      downloadFile: "下载",
      noTicker: "请输入公司代码",
      error: "请求失败，请稍后重试。",
    },
    macro: {
      eyebrow: "市场宏观",
      title: "宏观看板",
      loading: "加载中…",
      empty: "暂无宏观数据，请先在控制中心或后台刷新 FRED 数据。",
      error: "加载失败，请稍后重试。",
      range_3m: "3个月",
      range_6m: "6个月",
      range_1y: "1年",
      range_3y: "3年",
      previous: "前值",
      updated: "更新",
      source: "来源",
      judge_bullish: "利好",
      judge_neutral: "中性",
      judge_bearish: "利空",
      warnRange: "预警区间",
      warnLow: "低位",
      warnHigh: "高位",
      zone_high: "高位",
      zone_normal: "正常",
      zone_low: "低位",
      forecast: "预测",
    },
    calendar: {
      eyebrow: "财经日历",
      title: "核心财经事件日历",
      loading: "加载中…",
      error: "加载失败，请稍后重试。",
      empty: "所选范围内暂无事件。",
      tzBeijing: "北京",
      tzEastern: "美东",
      cat_inflation: "通胀",
      cat_employment: "就业",
      cat_rates: "联邦利率",
      cat_growth: "经济增长",
      cat_earnings: "美股财报",
      preset_today: "今天",
      preset_week: "未来一周",
      preset_month: "未来一月",
      tracked: "关注代码",
      addTickerPlaceholder: "添加代码，如 AMD",
      add: "添加",
      trackedOnly: "仅看关注",
      allDay: "全天",
      colTime: "时间",
      colImportance: "重要性",
      colEvent: "事件",
      colPrevious: "前值",
      colForecast: "预期",
      colActual: "实际",
      colAssets: "影响资产",
      colSource: "来源",
      follow: "关注",
      followed: "已关注",
    },
    auth: {
      loginEyebrow: "欢迎回来",
      loginTitle: "登录 TradingRader",
      registerEyebrow: "新建工作区",
      registerTitle: "创建你的账号",
      email: "邮箱",
      password: "密码",
      displayName: "显示名称",
      emailPlaceholder: "you@example.com",
      passwordPlaceholder: "••••••••",
      displayNamePlaceholder: "你的名字",
      registerPasswordPlaceholder: "至少 8 个字符",
      signIn: "登录",
      signingIn: "登录中…",
      createAccount: "创建账号",
      creatingAccount: "创建中…",
      noAccount: "还没有账号？",
      haveAccount: "已经有账号了？",
      createOne: "立即注册",
      signInLink: "去登录",
      loginFailed: "登录失败，请稍后重试。",
      registerFailed: "注册失败，请稍后重试。",
    },
  },
  en: {
    app: {
      localeLabel: "Language",
      switchToChinese: "切换到中文",
      switchToEnglish: "Switch to English",
    },
    nav: {
      feed: "Latest Updates",
      dataSources: "Sources",
      controlCenter: "Control Center",
      contentAnalysis: "Research Analysis",
      signOut: "Sign out",
      searchPlaceholder: "Search sources, keywords…",
      sectionSources: "Sources",
      sectionAnalysis: "Analysis",
      socialMedia: "Social Media",
      financeVideo: "Finance Video",
      financeNews: "Finance News",
      macroMarket: "Market Macro",
      financeCalendar: "Finance Calendar",
      srcJin10: "Jin10",
      srcYahoo: "Yahoo Finance",
      srcBloomberg: "Bloomberg",
      srcReuters: "Reuters",
      macroRates: "Rates & Policy",
      macroInflation: "Inflation",
      macroGrowth: "Growth",
      macroEmployment: "Employment",
      macroLiquidity: "Liquidity",
      macroRisk: "Risk Appetite",
      calCentralBank: "Central Bank",
      calIndustry: "Industry Events",
      calEarnings: "Earnings",
      stockAnalysis: "Stock Analysis",
      marketAnalysis: "Market Analysis",
      memberOnline: "Pro · Online",
    },
    feed: {
      eyebrow: "Feed",
      title: "Latest Updates",
      sortByTime: "By Time",
      sortByAuthor: "By Author",
      loading: "Loading…",
      empty: "No videos yet. Add a source and trigger a crawl first.",
      fetchError: "Failed to load. Please try again.",
      prevPage: "Prev",
      nextPage: "Next",
      tabVideos: "Videos",
      tabArticles: "Articles",
      tabNews: "News",
      tabMarket: "Market",
      viewAll: "View all",
      showMore: "Show more",
      showLess: "Show less",
      viewOriginal: "View original",
      comingSoon: "Coming soon",
      backToFeed: "← Back to Feed",
      itemsUnit: "items",
      refresh: "Refresh",
      today: "Today",
      yesterday: "Yesterday",
      statTotal: "items",
      statSources: "sources",
      placeholderHint: "This section will connect to live data soon — showing sample content for now.",
      placeholderSummary: "Once data sources are connected, real-time content from finance news and macro market channels will appear here.",
    },
    dataSources: {
      eyebrow: "Sources",
      title: "Source Management",
      addPlaceholder: "Paste an X or YouTube profile URL",
      addButton: "Add",
      adding: "Adding…",
      empty: "No sources yet. Paste a channel URL to get started.",
      loading: "Loading…",
      fetchError: "Failed to load. Please try again.",
      addError: "Failed to add. Check the URL format or your connection.",
      initializing: "Initializing…",
      deleteConfirm: "Delete this source?",
      notePlaceholder: "Note (optional)",
      categoryPlaceholder: "Category (optional)",
      contentTypeLabel: "Content type",
      editTitle: "Edit source",
      save: "Save",
      cancel: "Cancel",
      starred: "Star",
      unstar: "Unstar",
      edit: "Edit",
      delete: "Delete",
      tabVideos: "Videos",
      tabArticles: "Articles",
      tabNews: "News",
      tabMarket: "Market",
      comingSoon: "This section is coming soon",
      platformYoutube: "YouTube",
      platformTwitter: "X",
      builtinFinanceNews: "Jin10 is a built-in source and syncs latest flashes every 10 minutes.",
      platformWechat: "WeChat",
      platformWebsite: "Website",
    },
    contentAnalysis: {
      eyebrow: "Research Analysis",
      title: "Research Analysis",
      description: "AI-powered content analysis and investment insights — coming soon.",
    },
    stockAnalysis: {
      eyebrow: "Stock Analysis",
      title: "Fundamentals & Filings Download",
      description: "Enter a US ticker to fetch and download its financial statements, filings and analyst estimates.",
      tickerPlaceholder: "Ticker, e.g. AAPL",
      sourcesLabel: "Sources:",
      downloadBtn: "Download",
      downloading: "Downloading…",
      files: "files",
      skipped: "Skipped",
      colType: "Type",
      colTitle: "Title",
      colPeriod: "Period",
      colSize: "Size",
      downloadFile: "Download",
      noTicker: "Please enter a ticker",
      error: "Request failed, please try again.",
    },
    macro: {
      eyebrow: "Market Macro",
      title: "Macro Dashboard",
      loading: "Loading…",
      empty: "No macro data yet. Refresh FRED data first.",
      error: "Failed to load. Please try again.",
      range_3m: "3M",
      range_6m: "6M",
      range_1y: "1Y",
      range_3y: "3Y",
      previous: "Prev",
      updated: "Updated",
      source: "Source",
      judge_bullish: "Bullish",
      judge_neutral: "Neutral",
      judge_bearish: "Bearish",
      warnRange: "Alert range",
      warnLow: "Low",
      warnHigh: "High",
      zone_high: "High",
      zone_normal: "Normal",
      zone_low: "Low",
      forecast: "Forecast",
    },
    calendar: {
      eyebrow: "Calendar",
      title: "Financial Events Calendar",
      loading: "Loading…",
      error: "Failed to load. Please try again.",
      empty: "No events in the selected range.",
      tzBeijing: "Beijing",
      tzEastern: "US East",
      cat_inflation: "Inflation",
      cat_employment: "Employment",
      cat_rates: "Fed Rates",
      cat_growth: "Growth",
      cat_earnings: "Earnings",
      preset_today: "Today",
      preset_week: "Next 7d",
      preset_month: "Next 30d",
      tracked: "Tracked",
      addTickerPlaceholder: "Add ticker, e.g. AMD",
      add: "Add",
      trackedOnly: "Tracked only",
      allDay: "All day",
      colTime: "Time",
      colImportance: "Impact",
      colEvent: "Event",
      colPrevious: "Prev",
      colForecast: "Forecast",
      colActual: "Actual",
      colAssets: "Assets",
      colSource: "Source",
      follow: "Follow",
      followed: "Following",
    },
    auth: {
      loginEyebrow: "Welcome back",
      loginTitle: "Sign in to TradingRader",
      registerEyebrow: "New workspace",
      registerTitle: "Create your account",
      email: "Email",
      password: "Password",
      displayName: "Display name",
      emailPlaceholder: "you@example.com",
      passwordPlaceholder: "••••••••",
      displayNamePlaceholder: "Your name",
      registerPasswordPlaceholder: "At least 8 characters",
      signIn: "Sign in",
      signingIn: "Signing in…",
      createAccount: "Create account",
      creatingAccount: "Creating account…",
      noAccount: "Don't have an account?",
      haveAccount: "Already have an account?",
      createOne: "Create one",
      signInLink: "Sign in",
      loginFailed: "Login failed. Please try again.",
      registerFailed: "Registration failed. Please try again.",
    },
  },
} as const;

type MessageTree = typeof messages;
type MessageKey =
  | "app.localeLabel"
  | "app.switchToChinese"
  | "app.switchToEnglish"
  | "nav.dataSources"
  | "nav.controlCenter"
  | "nav.contentAnalysis"
  | "nav.signOut"
  | "nav.searchPlaceholder"
  | "nav.sectionSources"
  | "nav.sectionAnalysis"
  | "nav.socialMedia"
  | "nav.financeVideo"
  | "nav.financeNews"
  | "nav.macroMarket"
  | "nav.financeCalendar"
  | "nav.srcJin10"
  | "nav.srcYahoo"
  | "nav.srcBloomberg"
  | "nav.srcReuters"
  | "nav.macroRates"
  | "nav.macroInflation"
  | "nav.macroGrowth"
  | "nav.macroEmployment"
  | "nav.macroLiquidity"
  | "nav.macroRisk"
  | "nav.calCentralBank"
  | "nav.calIndustry"
  | "nav.calEarnings"
  | "nav.stockAnalysis"
  | "nav.marketAnalysis"
  | "nav.memberOnline"
  | "feed.eyebrow"
  | "feed.title"
  | "feed.sortByTime"
  | "feed.sortByAuthor"
  | "feed.loading"
  | "feed.empty"
  | "feed.fetchError"
  | "feed.prevPage"
  | "feed.nextPage"
  | "feed.tabVideos"
  | "feed.tabArticles"
  | "feed.tabNews"
  | "feed.tabMarket"
  | "feed.viewAll"
  | "feed.showMore"
  | "feed.showLess"
  | "feed.viewOriginal"
  | "feed.comingSoon"
  | "feed.backToFeed"
  | "feed.itemsUnit"
  | "feed.refresh"
  | "feed.today"
  | "feed.yesterday"
  | "feed.statTotal"
  | "feed.statSources"
  | "feed.placeholderHint"
  | "feed.placeholderSummary"
  | "dataSources.eyebrow"
  | "dataSources.title"
  | "dataSources.addPlaceholder"
  | "dataSources.addButton"
  | "dataSources.adding"
  | "dataSources.empty"
  | "dataSources.loading"
  | "dataSources.fetchError"
  | "dataSources.addError"
  | "dataSources.initializing"
  | "dataSources.deleteConfirm"
  | "dataSources.notePlaceholder"
  | "dataSources.categoryPlaceholder"
  | "dataSources.contentTypeLabel"
  | "dataSources.editTitle"
  | "dataSources.save"
  | "dataSources.cancel"
  | "dataSources.starred"
  | "dataSources.unstar"
  | "dataSources.edit"
  | "dataSources.delete"
  | "dataSources.tabVideos"
  | "dataSources.tabArticles"
  | "dataSources.tabNews"
  | "dataSources.tabMarket"
  | "dataSources.comingSoon"
  | "dataSources.platformYoutube"
  | "dataSources.platformTwitter"
  | "dataSources.builtinFinanceNews"
  | "dataSources.platformWechat"
  | "dataSources.platformWebsite"
  | "contentAnalysis.eyebrow"
  | "contentAnalysis.title"
  | "contentAnalysis.description"
  | "stockAnalysis.eyebrow"
  | "stockAnalysis.title"
  | "stockAnalysis.description"
  | "stockAnalysis.tickerPlaceholder"
  | "stockAnalysis.sourcesLabel"
  | "stockAnalysis.downloadBtn"
  | "stockAnalysis.downloading"
  | "stockAnalysis.files"
  | "stockAnalysis.skipped"
  | "stockAnalysis.colType"
  | "stockAnalysis.colTitle"
  | "stockAnalysis.colPeriod"
  | "stockAnalysis.colSize"
  | "stockAnalysis.downloadFile"
  | "stockAnalysis.noTicker"
  | "stockAnalysis.error"
  | "macro.eyebrow"
  | "macro.title"
  | "macro.loading"
  | "macro.empty"
  | "macro.error"
  | "macro.range_3m"
  | "macro.range_6m"
  | "macro.range_1y"
  | "macro.range_3y"
  | "macro.previous"
  | "macro.updated"
  | "macro.source"
  | "macro.judge_bullish"
  | "macro.judge_neutral"
  | "macro.judge_bearish"
  | "macro.warnRange"
  | "macro.warnLow"
  | "macro.warnHigh"
  | "macro.zone_high"
  | "macro.zone_normal"
  | "macro.zone_low"
  | "macro.forecast"
  | "calendar.eyebrow"
  | "calendar.title"
  | "calendar.loading"
  | "calendar.error"
  | "calendar.empty"
  | "calendar.tzBeijing"
  | "calendar.tzEastern"
  | "calendar.cat_inflation"
  | "calendar.cat_employment"
  | "calendar.cat_rates"
  | "calendar.cat_growth"
  | "calendar.cat_earnings"
  | "calendar.preset_today"
  | "calendar.preset_week"
  | "calendar.preset_month"
  | "calendar.tracked"
  | "calendar.addTickerPlaceholder"
  | "calendar.add"
  | "calendar.trackedOnly"
  | "calendar.allDay"
  | "calendar.colTime"
  | "calendar.colImportance"
  | "calendar.colEvent"
  | "calendar.colPrevious"
  | "calendar.colForecast"
  | "calendar.colActual"
  | "calendar.colAssets"
  | "calendar.colSource"
  | "calendar.follow"
  | "calendar.followed"
  | "auth.loginEyebrow"
  | "auth.loginTitle"
  | "auth.registerEyebrow"
  | "auth.registerTitle"
  | "auth.email"
  | "auth.password"
  | "auth.displayName"
  | "auth.emailPlaceholder"
  | "auth.passwordPlaceholder"
  | "auth.displayNamePlaceholder"
  | "auth.registerPasswordPlaceholder"
  | "auth.signIn"
  | "auth.signingIn"
  | "auth.createAccount"
  | "auth.creatingAccount"
  | "auth.noAccount"
  | "auth.haveAccount"
  | "auth.createOne"
  | "auth.signInLink"
  | "auth.loginFailed"
  | "auth.registerFailed";

function loadInitialLocale(): Locale {
  const saved = localStorage.getItem(LOCALE_KEY);
  return saved === "zh-CN" || saved === "en" ? saved : defaultLocale;
}

const locale = ref<Locale>(loadInitialLocale());

watch(
  locale,
  (value) => {
    localStorage.setItem(LOCALE_KEY, value);
    document.documentElement.lang = value;
  },
  { immediate: true },
);

function getMessageValue(tree: MessageTree[Locale], key: MessageKey): string {
  return key.split(".").reduce((current, part) => current[part as keyof typeof current], tree as any) as string;
}

export function useI18n() {
  const currentLocale = computed(() => locale.value);

  function setLocale(value: Locale) {
    locale.value = value;
  }

  function toggleLocale() {
    locale.value = locale.value === "zh-CN" ? "en" : "zh-CN";
  }

  function t(key: MessageKey) {
    return getMessageValue(messages[locale.value], key);
  }

  return {
    locale: currentLocale,
    setLocale,
    toggleLocale,
    t,
  };
}
