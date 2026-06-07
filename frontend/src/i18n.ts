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
      feed: "动态资讯",
      dataSources: "信源管理",
      controlCenter: "控制中心",
      contentAnalysis: "投研分析",
      signOut: "退出登录",
      searchPlaceholder: "搜索信源、关键词…",
      sectionViews: "视图",
      allFeed: "所有信息流",
      unread: "未读",
      starred: "已收藏",
      readLater: "稍后阅读",
      sectionSources: "信源",
      sectionAnalysis: "分析",
      personalSources: "个人信源",
      financeNews: "金融时讯",
      macroMarket: "市场宏观",
      financeCalendar: "金融日历",
      macroIndicators: "宏观指标",
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
      addPlaceholder: "粘贴 Bilibili 或 YouTube 主页链接",
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
      platformBilibili: "Bilibili",
      platformYoutube: "YouTube",
      platformTwitter: "X",
      platformWechat: "公众号",
      platformWebsite: "网站",
    },
    contentAnalysis: {
      eyebrow: "投研分析",
      title: "投研分析",
      description: "基于大模型的视频内容分析与投研洞察，即将上线。",
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
      sectionViews: "Views",
      allFeed: "All Feed",
      unread: "Unread",
      starred: "Starred",
      readLater: "Read Later",
      sectionSources: "Sources",
      sectionAnalysis: "Analysis",
      personalSources: "Personal Sources",
      financeNews: "Finance News",
      macroMarket: "Market Macro",
      financeCalendar: "Finance Calendar",
      macroIndicators: "Macro Indicators",
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
      addPlaceholder: "Paste a Bilibili or YouTube channel URL",
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
      platformBilibili: "Bilibili",
      platformYoutube: "YouTube",
      platformTwitter: "X",
      platformWechat: "WeChat",
      platformWebsite: "Website",
    },
    contentAnalysis: {
      eyebrow: "Research Analysis",
      title: "Research Analysis",
      description: "AI-powered content analysis and investment insights — coming soon.",
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
  | "nav.feed"
  | "nav.dataSources"
  | "nav.controlCenter"
  | "nav.contentAnalysis"
  | "nav.signOut"
  | "nav.searchPlaceholder"
  | "nav.sectionViews"
  | "nav.allFeed"
  | "nav.unread"
  | "nav.starred"
  | "nav.readLater"
  | "nav.sectionSources"
  | "nav.sectionAnalysis"
  | "nav.personalSources"
  | "nav.financeNews"
  | "nav.macroMarket"
  | "nav.financeCalendar"
  | "nav.macroIndicators"
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
  | "dataSources.platformBilibili"
  | "dataSources.platformYoutube"
  | "dataSources.platformTwitter"
  | "dataSources.platformWechat"
  | "dataSources.platformWebsite"
  | "contentAnalysis.eyebrow"
  | "contentAnalysis.title"
  | "contentAnalysis.description"
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
