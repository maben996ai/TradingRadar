import { createRouter, createWebHistory } from "vue-router";

import AppShell from "../components/layout/AppShell.vue";
import { useAuthStore } from "../stores/auth";
import ContentAnalysisView from "../views/ContentAnalysisView.vue";
import ControlCenterView from "../views/ControlCenterView.vue";
import DataSourcesView from "../views/DataSourcesView.vue";
import HomeView from "../views/HomeView.vue";
import LoginView from "../views/LoginView.vue";
import CalendarView from "../views/CalendarView.vue";
import MacroMarketView from "../views/MacroMarketView.vue";
import PlatformFeedView from "../views/PlatformFeedView.vue";
import RegisterView from "../views/RegisterView.vue";
import SourceFeedView from "../views/SourceFeedView.vue";
import StockAnalysisView from "../views/StockAnalysisView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/register", name: "register", component: RegisterView, meta: { public: true } },
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", name: "home", component: HomeView },
        { path: "feed/:platform", name: "platform-feed", component: PlatformFeedView },
        { path: "source/:sourceId", name: "source-feed", component: SourceFeedView },
        { path: "sources", name: "data-sources", component: DataSourcesView },
        { path: "macro-market", name: "macro-market", component: MacroMarketView },
        { path: "calendar", name: "calendar", component: CalendarView },
        { path: "creators", redirect: "/sources" },
        { path: "author/:creatorId", redirect: (to) => `/source/${to.params.creatorId}` },
        { path: "content-analysis", name: "content-analysis", component: ContentAnalysisView },
        { path: "stock-analysis", name: "stock-analysis", component: StockAnalysisView },
        { path: "control-center", name: "control-center", component: ControlCenterView },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore();

  if (authStore.isAuthenticated && !authStore.user) {
    await authStore.fetchUser();
  }

  if (!to.meta.public && !authStore.isAuthenticated) {
    return { name: "login" };
  }

  if (to.meta.public && authStore.isAuthenticated) {
    return { path: "/" };
  }
});
