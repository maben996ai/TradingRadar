<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-logo"></div>
        <div class="brand-name">Trading<span>Rader</span></div>
      </div>

      <div class="sidebar-search">
        <div class="search-box">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
          <input type="text" :placeholder="t('nav.searchPlaceholder')" />
          <kbd>⌘K</kbd>
        </div>
      </div>

      <nav class="nav">
        <!-- 视图 -->
        <div class="nav-section">
          <div class="nav-section-title">{{ t("nav.sectionViews") }}</div>
          <RouterLink to="/" class="nav-item" active-class="nav-noop" exact-active-class="active">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 6h18M3 18h18" /></svg></span>
            <span class="nav-item-label">{{ t("nav.allFeed") }}</span>
          </RouterLink>
          <div class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /></svg></span>
            <span class="nav-item-label">{{ t("nav.unread") }}</span>
            <span class="nav-item-count">14</span>
          </div>
          <div class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg></span>
            <span class="nav-item-label">{{ t("nav.starred") }}</span>
            <span class="nav-item-count">8</span>
          </div>
          <div class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg></span>
            <span class="nav-item-label">{{ t("nav.readLater") }}</span>
            <span class="nav-item-count">3</span>
          </div>
        </div>

        <!-- 信源 -->
        <div class="nav-section">
          <div class="nav-section-title">
            <span>{{ t("nav.sectionSources") }}</span>
            <button :title="t('nav.dataSources')" @click="router.push('/sources')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14" /></svg>
            </button>
          </div>

          <RouterLink to="/sources" class="nav-item">
            <span class="nav-item-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="8.5" cy="7" r="4" /><path d="M20 8v6M23 11h-6" /></svg></span>
            <span class="nav-item-label">{{ t("nav.dataSources") }}</span>
          </RouterLink>

          <!-- 以下为静态占位分组 -->
          <template v-for="group in placeholderGroups" :key="group.label">
            <div class="nav-item expandable" @click="toggleExpand(group.label)">
              <span class="nav-item-toggle" :class="{ expanded: expanded[group.label] }">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6" /></svg>
              </span>
              <span class="nav-item-icon" v-html="group.icon"></span>
              <span class="nav-item-label">{{ group.label }}</span>
              <span class="nav-item-count">{{ group.count }}</span>
            </div>
            <div class="nav-children" :class="{ expanded: expanded[group.label] }">
              <div v-for="child in group.children" :key="child.label" class="nav-child">
                <span class="nav-item-icon"><span class="dot" :class="child.dot" :style="child.color ? `background:${child.color}` : ''"></span></span>
                <span class="nav-item-label">{{ child.label }}</span>
                <span v-if="child.count" class="nav-item-count">{{ child.count }}</span>
              </div>
            </div>
          </template>
        </div>

        <!-- 分析 -->
        <div class="nav-section">
          <div class="nav-section-title">{{ t("nav.sectionAnalysis") }}</div>
          <RouterLink to="/content-analysis" class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></svg></span>
            <span class="nav-item-label">{{ t("nav.contentAnalysis") }}</span>
          </RouterLink>
          <div class="nav-children expanded">
            <div class="nav-child">
              <span class="nav-item-icon"><span class="dot" style="background:#a855f7"></span></span>
              <span class="nav-item-label">{{ t("nav.stockAnalysis") }}</span>
              <span class="nav-item-count">12</span>
            </div>
            <div class="nav-child">
              <span class="nav-item-icon"><span class="dot" style="background:#06b6d4"></span></span>
              <span class="nav-item-label">{{ t("nav.marketAnalysis") }}</span>
              <span class="nav-item-count">6</span>
            </div>
          </div>
          <RouterLink to="/control-center" class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg></span>
            <span class="nav-item-label">{{ t("nav.controlCenter") }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="locale-toggle">
        <button
          class="locale-link"
          :class="{ 'locale-link-active': locale === 'zh-CN' }"
          @click="setLocale('zh-CN')"
        >中文</button>
        <span class="locale-sep">/</span>
        <button
          class="locale-link"
          :class="{ 'locale-link-active': locale === 'en' }"
          @click="setLocale('en')"
        >EN</button>
      </div>

      <div class="user-area">
        <div class="user-avatar">{{ userInitials }}</div>
        <div class="user-info">
          <div class="user-name">{{ authStore.user?.display_name ?? authStore.user?.email }}</div>
          <div class="user-status">{{ t("nav.memberOnline") }}</div>
        </div>
        <button :title="t('nav.controlCenter')" @click="router.push('/control-center')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
        </button>
        <button :title="t('nav.signOut')" @click="handleLogout">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
        </button>
      </div>
    </aside>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from "vue";
import { RouterLink, RouterView, useRouter } from "vue-router";

import { useI18n } from "../../i18n";
import { useAuthStore } from "../../stores/auth";

const router = useRouter();
const authStore = useAuthStore();
const { t, locale, setLocale } = useI18n();

const expanded = reactive<Record<string, boolean>>({});

function toggleExpand(key: string) {
  expanded[key] = !expanded[key];
}

const userInitials = computed(() => {
  const name = authStore.user?.display_name ?? authStore.user?.email ?? "";
  return name.slice(0, 2).toUpperCase();
});

// 静态占位分组（后端暂未提供，仅用于呈现原型导航结构）
const placeholderGroups = computed(() => [
  {
    label: t("nav.personalSources"),
    count: "26",
    icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M20 8v6M23 11h-6"/></svg>',
    children: [
      { label: t("nav.financeNews"), dot: "dot-news", color: "", count: "9" },
      { label: "Twitter / X", dot: "dot-twitter", color: "", count: "" },
      { label: "YouTube", dot: "dot-youtube", color: "", count: "5" },
    ],
  },
  {
    label: t("nav.macroMarket"),
    count: "18",
    icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    children: [
      { label: t("nav.financeCalendar"), dot: "dot-calendar", color: "", count: "12" },
      { label: t("nav.macroIndicators"), dot: "dot-macro", color: "", count: "6" },
    ],
  },
]);

function handleLogout() {
  authStore.logout();
  router.push("/login");
}
</script>
