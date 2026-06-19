<template>
  <section class="panel content-analysis">
    <p class="eyebrow">{{ t("contentAnalysis.eyebrow") }}</p>
    <h2>{{ t("contentAnalysis.title") }}</h2>
    <p class="muted">{{ t("contentAnalysis.description") }}</p>

    <div class="ca-statusbar">
      <span :class="['ca-badge', status?.transcribe_available ? 'ok' : 'warn']">
        {{
          status?.transcribe_available
            ? `${t("contentAnalysis.backendLabel")}: ${status.transcribe_backend}`
            : t("contentAnalysis.backendUnavailable")
        }}
      </span>
      <span :class="['ca-badge', status?.youtube_logged_in ? 'ok' : 'muted-badge']">
        {{
          status?.youtube_logged_in
            ? t("contentAnalysis.youtubeLoggedIn")
            : t("contentAnalysis.youtubeNotLoggedIn")
        }}
      </span>
      <button class="ca-link" :disabled="loggingIn" @click="onLoginBrowser">
        {{ loggingIn ? "…" : t("contentAnalysis.importBrowser") }}
      </button>
    </div>
    <p v-if="loginMsg" class="muted ca-hint">{{ loginMsg }}</p>

    <div class="ca-form">
      <input
        v-model="url"
        class="ca-input"
        :placeholder="t('contentAnalysis.urlPlaceholder')"
        @keyup.enter="onDownload"
      />
      <select v-model="mode" class="ca-select">
        <option value="video">{{ t("contentAnalysis.modeVideo") }}</option>
        <option value="audio">{{ t("contentAnalysis.modeAudio") }}</option>
      </select>
      <button class="ca-btn" :disabled="downloading" @click="onDownload">
        {{ t("contentAnalysis.download") }}
      </button>
    </div>
    <p v-if="error" class="ca-error">{{ error }}</p>

    <div v-if="counts" class="ca-counts">
      <span>{{ t("contentAnalysis.countSources") }}: {{ counts.sources ?? 0 }}</span>
      <span>{{ t("contentAnalysis.countVideo") }}: {{ counts.video ?? 0 }}</span>
      <span>{{ t("contentAnalysis.countAudio") }}: {{ counts.audio ?? 0 }}</span>
      <span>{{ t("contentAnalysis.countText") }}: {{ counts.text ?? 0 }}</span>
    </div>

    <input
      v-model="query"
      class="ca-input ca-search"
      :placeholder="t('contentAnalysis.searchPlaceholder')"
      @input="onSearch"
    />

    <p v-if="!sources.length" class="muted ca-empty">{{ t("contentAnalysis.empty") }}</p>

    <div v-else class="ca-sources">
      <div v-for="s in sources" :key="s.id" class="ca-source">
        <div class="ca-source-head">
          <a :href="s.url" target="_blank" rel="noopener" class="ca-source-title">{{ s.title }}</a>
          <span v-if="s.author" class="muted ca-author">{{ s.author }}</span>
          <button class="ca-link ca-del" @click="onDeleteSource(s.id)">
            {{ t("contentAnalysis.delete") }}
          </button>
        </div>
        <div class="ca-artifacts">
          <div v-for="a in s.artifacts" :key="a.id" class="ca-artifact">
            <span class="ca-type">{{ a.type }}</span>
            <span :class="['ca-status', `st-${a.status}`]">{{ statusLabel(a.status) }}</span>
            <span v-if="a.status === 'running'" class="ca-progress">
              {{ a.progress.toFixed(0) }}%
            </span>
            <span v-if="a.error" class="ca-err" :title="a.error">{{ a.error }}</span>
            <span class="ca-actions">
              <button
                v-if="a.type !== 'text' && a.status === 'finished'"
                class="ca-link"
                :disabled="!status?.transcribe_available"
                @click="onTranscribe(a.id)"
              >
                {{ t("contentAnalysis.transcribe") }}
              </button>
              <button
                v-if="a.type === 'text' && a.status === 'finished'"
                class="ca-link"
                @click="onViewText(a.id)"
              >
                {{ t("contentAnalysis.viewText") }}
              </button>
              <button
                v-if="a.status === 'finished'"
                class="ca-link"
                @click="onReveal(a.id)"
              >
                {{ t("contentAnalysis.openFolder") }}
              </button>
              <button
                v-if="['queued', 'running', 'processing'].includes(a.status)"
                class="ca-link"
                @click="onCancel(a.id)"
              >
                {{ t("contentAnalysis.cancel") }}
              </button>
              <button class="ca-link ca-del" @click="onDeleteArtifact(a.id)">
                {{ t("contentAnalysis.delete") }}
              </button>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="textPreview !== null" class="ca-modal" @click.self="textPreview = null">
      <div class="ca-modal-box">
        <div class="ca-modal-head">
          <strong>{{ t("contentAnalysis.textPreview") }}</strong>
          <button class="ca-link" @click="textPreview = null">
            {{ t("contentAnalysis.close") }}
          </button>
        </div>
        <pre class="ca-modal-text">{{ textPreview }}</pre>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import { contentAnalysisApi } from "../api/contentAnalysis";
import { useI18n, type MessageKey } from "../i18n";
import type { AnalysisSource, AnalysisStatus } from "../types";

const { t } = useI18n();

const url = ref("");
const mode = ref<"video" | "audio">("video");
const downloading = ref(false);
const error = ref("");
const sources = ref<AnalysisSource[]>([]);
const counts = ref<Record<string, number> | null>(null);
const status = ref<AnalysisStatus | null>(null);
const loggingIn = ref(false);
const loginMsg = ref("");
const textPreview = ref<string | null>(null);
const query = ref("");

let timer: number | undefined;
let searchTimer: number | undefined;

const hasActive = computed(() =>
  sources.value.some((s) =>
    s.artifacts.some((a) => ["queued", "running", "processing"].includes(a.status)),
  ),
);

const STATUS_KEYS: Record<string, MessageKey> = {
  queued: "contentAnalysis.statusQueued",
  running: "contentAnalysis.statusRunning",
  processing: "contentAnalysis.statusProcessing",
  finished: "contentAnalysis.statusFinished",
  error: "contentAnalysis.statusError",
  canceled: "contentAnalysis.statusCanceled",
};

function statusLabel(s: string): string {
  return STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s;
}


async function loadStatus() {
  try {
    status.value = (await contentAnalysisApi.status()).data;
  } catch {
    // 状态拉取失败不阻断
  }
}

async function loadList() {
  try {
    const { data } = await contentAnalysisApi.list(undefined, query.value.trim() || undefined);
    sources.value = data.sources;
    counts.value = data.counts;
  } catch {
    // 列表拉取失败不阻断
  }
}

function onSearch() {
  if (searchTimer) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadList, 300);
}

function schedulePoll() {
  if (timer) window.clearInterval(timer);
  timer = window.setInterval(() => {
    if (hasActive.value) loadList();
  }, 2000);
}

async function onDownload() {
  const link = url.value.trim();
  if (!link) return;
  downloading.value = true;
  error.value = "";
  try {
    await contentAnalysisApi.download(link, mode.value);
    url.value = "";
    await loadList();
  } catch {
    error.value = t("contentAnalysis.downloadFailed");
  } finally {
    downloading.value = false;
  }
}

async function onTranscribe(id: string) {
  try {
    await contentAnalysisApi.transcribe(id);
    await loadList();
  } catch {
    error.value = t("contentAnalysis.downloadFailed");
  }
}

async function onCancel(id: string) {
  await contentAnalysisApi.cancel(id);
  await loadList();
}

async function onReveal(id: string) {
  try {
    await contentAnalysisApi.reveal(id);
  } catch {
    error.value = t("contentAnalysis.downloadFailed");
  }
}

async function onDeleteArtifact(id: string) {
  if (!window.confirm(t("contentAnalysis.confirmDelete"))) return;
  await contentAnalysisApi.deleteArtifact(id, true);
  await loadList();
}

async function onDeleteSource(id: string) {
  if (!window.confirm(t("contentAnalysis.confirmDelete"))) return;
  await contentAnalysisApi.deleteSource(id, true);
  await loadList();
}

async function onViewText(id: string) {
  try {
    textPreview.value = await contentAnalysisApi.fetchText(id);
  } catch {
    error.value = t("contentAnalysis.downloadFailed");
  }
}

async function onLoginBrowser() {
  loggingIn.value = true;
  loginMsg.value = "";
  try {
    // 默认从当前浏览器（Chrome）导入 cookies，无需用户选择
    const { data } = await contentAnalysisApi.loginBrowser("chrome");
    loginMsg.value =
      data.message ||
      (data.ok ? t("contentAnalysis.loginSuccess") : t("contentAnalysis.loginFailed"));
    await loadStatus();
  } catch {
    loginMsg.value = t("contentAnalysis.loginFailed");
  } finally {
    loggingIn.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadStatus(), loadList()]);
  schedulePoll();
});

onUnmounted(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<style scoped>
.content-analysis h2 {
  margin: 0.2rem 0 0.4rem;
}
.ca-statusbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  margin: 0.8rem 0;
}
.ca-badge {
  font-size: 0.78rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
}
.ca-badge.ok {
  background: rgba(22, 163, 74, 0.14);
  color: #16a34a;
}
.ca-badge.warn {
  background: rgba(220, 38, 38, 0.14);
  color: #dc2626;
}
.ca-cookies {
  margin: 0.4rem 0 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 560px;
}
.ca-textarea {
  width: 100%;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border, #d0d7de);
  border-radius: 8px;
  font-family: monospace;
  font-size: 0.8rem;
}
.ca-form {
  display: flex;
  gap: 0.6rem;
  margin: 0.6rem 0 0.4rem;
  flex-wrap: wrap;
}
.ca-input {
  flex: 1 1 320px;
  padding: 0.55rem 0.8rem;
  border: 1px solid var(--border, #d0d7de);
  border-radius: 8px;
  font-size: 0.95rem;
}
.ca-select {
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border, #d0d7de);
  border-radius: 8px;
}
.ca-btn {
  padding: 0.55rem 1.2rem;
  border: none;
  border-radius: 8px;
  background: var(--accent, #2563eb);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.ca-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.ca-error {
  color: #dc2626;
  margin: 0.4rem 0;
}
.ca-search {
  width: 100%;
  margin: 0.2rem 0 0.8rem;
}
.ca-counts {
  display: flex;
  gap: 1rem;
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
  margin: 0.6rem 0;
}
.ca-empty {
  margin-top: 1rem;
}
.ca-sources {
  margin-top: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}
.ca-source {
  border: 1px solid var(--border, #eaecef);
  border-radius: 10px;
  padding: 0.7rem 0.9rem;
}
.ca-source-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.ca-source-title {
  font-weight: 700;
  color: var(--text, #1f2328);
  text-decoration: none;
}
.ca-author {
  font-size: 0.82rem;
}
.ca-artifacts {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.ca-artifact {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  font-size: 0.86rem;
}
.ca-type {
  width: 48px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--muted, #6b7280);
}
.ca-status {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: rgba(107, 114, 128, 0.15);
}
.st-finished {
  background: rgba(22, 163, 74, 0.14);
  color: #16a34a;
}
.st-running,
.st-processing {
  background: rgba(37, 99, 235, 0.14);
  color: #2563eb;
}
.st-error {
  background: rgba(220, 38, 38, 0.14);
  color: #dc2626;
}
.ca-progress {
  font-size: 0.78rem;
  color: #2563eb;
}
.ca-err {
  color: #dc2626;
  font-size: 0.78rem;
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: help;
}
.ca-actions {
  display: flex;
  gap: 0.6rem;
  margin-left: auto;
}
.ca-link {
  border: none;
  background: none;
  color: var(--accent, #2563eb);
  cursor: pointer;
  font-weight: 600;
  padding: 0;
  font-size: 0.84rem;
  text-decoration: none;
}
.ca-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ca-del {
  color: #dc2626;
}
.ca-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.ca-modal-box {
  background: var(--bg, #fff);
  border-radius: 10px;
  width: min(720px, 90vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding: 1rem;
}
.ca-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}
.ca-modal-text {
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.88rem;
  line-height: 1.5;
}
</style>
