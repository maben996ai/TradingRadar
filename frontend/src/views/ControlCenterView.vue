<template>
  <section class="stack">
    <div class="panel">
      <p class="eyebrow">通知配置</p>
      <h2>飞书 Webhook</h2>
      <p class="muted">配置飞书群机器人 Webhook，抓取到新内容时同步推送到多个群。</p>

      <!-- 已有 webhook 列表 -->
      <el-table :data="webhooks" style="margin-top: 16px" v-loading="loading">
        <el-table-column label="群名称" prop="name" min-width="120" />
        <el-table-column label="Webhook 地址" prop="webhook_url" min-width="300">
          <template #default="{ row }">
            <span class="muted" style="font-size: 12px; word-break: break-all">{{ row.webhook_url }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="(val: boolean) => toggleEnabled(row, val)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" :loading="testingId === row.id" @click="sendTest(row)">测试</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增表单 -->
      <el-form :model="form" inline style="margin-top: 16px">
        <el-form-item label="群名称">
          <el-input v-model="form.name" placeholder="港股研究群" style="width: 140px" />
        </el-form-item>
        <el-form-item label="Webhook 地址">
          <el-input
            v-model="form.webhook_url"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
            style="width: 360px"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="create">添加</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="panel">
      <p class="eyebrow">API 用量</p>
      <h2>额度查看</h2>
      <p class="muted">跳转到各数据源控制台，查看接口调用量与剩余额度。</p>

      <div class="quota-links">
        <a
          v-for="link in quotaLinks"
          :key="link.url"
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          class="quota-link"
        >
          <div class="quota-link-main">
            <span class="quota-link-name">{{ link.name }}</span>
            <span class="muted quota-link-desc">{{ link.desc }}</span>
          </div>
          <span class="quota-link-arrow">↗</span>
        </a>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { webhooksApi, type FeishuWebhook } from "../api/webhooks";

const webhooks = ref<FeishuWebhook[]>([]);
const loading = ref(false);
const creating = ref(false);
const testingId = ref<string | null>(null);
const form = ref({ name: "", webhook_url: "" });

const quotaLinks = [
  {
    name: "TwitterAPI.io",
    desc: "X/Twitter 抓取额度与用量",
    url: "https://twitterapi.io/zh-CN/dashboard",
  },
  {
    name: "FMP",
    desc: "Financial Modeling Prep 接口额度与用量",
    url: "https://site.financialmodelingprep.com/developer/docs/dashboard",
  },
];

async function load() {
  loading.value = true;
  try {
    const res = await webhooksApi.list();
    webhooks.value = res.data;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

async function create() {
  if (!form.value.name || !form.value.webhook_url) {
    ElMessage.warning("请填写群名称和 Webhook 地址");
    return;
  }
  creating.value = true;
  try {
    await webhooksApi.create(form.value);
    form.value = { name: "", webhook_url: "" };
    ElMessage.success("添加成功");
    await load();
  } catch {
    ElMessage.error("添加失败");
  } finally {
    creating.value = false;
  }
}

async function toggleEnabled(row: FeishuWebhook, val: boolean) {
  try {
    await webhooksApi.update(row.id, { enabled: val });
    row.enabled = val;
  } catch {
    ElMessage.error("更新失败");
  }
}

async function sendTest(row: FeishuWebhook) {
  testingId.value = row.id;
  try {
    await webhooksApi.test(row.id);
    ElMessage.success(`测试消息已发送到「${row.name}」`);
  } catch {
    ElMessage.error("发送失败，请检查 Webhook 地址");
  } finally {
    testingId.value = null;
  }
}

async function remove(row: FeishuWebhook) {
  await ElMessageBox.confirm(`确认删除「${row.name}」？`, "删除确认", { type: "warning" });
  try {
    await webhooksApi.delete(row.id);
    ElMessage.success("已删除");
    await load();
  } catch {
    ElMessage.error("删除失败");
  }
}
</script>
