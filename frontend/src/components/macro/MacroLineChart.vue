<template>
  <div class="macro-chart" @mousemove="onMove" @mouseleave="hoverIndex = null">
    <template v-if="points.length > 1">
      <svg class="macro-chart-svg" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none">
        <defs>
          <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
            <stop offset="100%" :stop-color="color" stop-opacity="0.02" />
          </linearGradient>
        </defs>

        <!-- 水平网格线 -->
        <line
          v-for="g in GRID_FRACTIONS"
          :key="g"
          x1="0"
          :x2="W"
          :y1="g * H"
          :y2="g * H"
          class="macro-grid-line"
          vector-effect="non-scaling-stroke"
        />

        <!-- 阈值虚线 -->
        <line
          v-if="highY !== null"
          x1="0"
          :x2="W"
          :y1="highY"
          :y2="highY"
          class="macro-th-line macro-th-line-high"
          vector-effect="non-scaling-stroke"
        />
        <line
          v-if="lowY !== null"
          x1="0"
          :x2="W"
          :y1="lowY"
          :y2="lowY"
          class="macro-th-line macro-th-line-low"
          vector-effect="non-scaling-stroke"
        />

        <path :d="areaPath" :fill="`url(#${gradientId})`" />
        <path
          :d="linePath"
          fill="none"
          :stroke="color"
          stroke-width="2"
          vector-effect="non-scaling-stroke"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <line
          v-if="hoverIndex !== null"
          :x1="coords[hoverIndex].x"
          :x2="coords[hoverIndex].x"
          y1="0"
          :y2="H"
          class="macro-chart-guide"
          vector-effect="non-scaling-stroke"
        />
      </svg>

      <!-- 坐标极值标注 -->
      <span class="macro-axis macro-axis-max">{{ formatValue(domainMax) }}</span>
      <span class="macro-axis macro-axis-min">{{ formatValue(domainMin) }}</span>

      <!-- 阈值标签 -->
      <span
        v-if="highY !== null"
        class="macro-th-tag macro-th-tag-high"
        :style="{ top: `${(highY / H) * 100}%` }"
      >{{ high!.toLocaleString() }}</span>
      <span
        v-if="lowY !== null"
        class="macro-th-tag macro-th-tag-low"
        :style="{ top: `${(lowY / H) * 100}%` }"
      >{{ low!.toLocaleString() }}</span>

      <!-- 端点 -->
      <span
        class="macro-dot-end"
        :style="{
          left: `${(coords[coords.length - 1].x / W) * 100}%`,
          top: `${(coords[coords.length - 1].y / H) * 100}%`,
          background: color,
        }"
      />

      <!-- hover 圆点 + tooltip -->
      <template v-if="hoverIndex !== null">
        <span
          class="macro-dot-hover"
          :style="{
            left: `${(coords[hoverIndex].x / W) * 100}%`,
            top: `${(coords[hoverIndex].y / H) * 100}%`,
            background: color,
          }"
        />
        <div
          class="macro-chart-tip"
          :style="{ left: `${(hoverIndex / (points.length - 1)) * 100}%` }"
        >
          <span class="macro-chart-tip-val">{{ formatValue(points[hoverIndex].value) }}{{ unitLabel }}</span>
          <span class="macro-chart-tip-date">{{ points[hoverIndex].date }}</span>
        </div>
      </template>
    </template>
    <p v-else class="macro-chart-empty">{{ emptyText }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import type { MacroJudgment, MacroPoint } from "../../types";

const props = withDefaults(
  defineProps<{
    points: MacroPoint[];
    judgment: MacroJudgment;
    decimals?: number;
    unitLabel?: string;
    emptyText?: string;
    high?: number | null;
    low?: number | null;
  }>(),
  { decimals: 2, unitLabel: "", emptyText: "暂无数据", high: null, low: null }
);

const W = 320;
const H = 150;
const PAD_Y = 12;
const GRID_FRACTIONS = [0.25, 0.5, 0.75];

const JUDGMENT_COLORS: Record<MacroJudgment, string> = {
  bullish: "#22c55e",
  neutral: "#64748b",
  bearish: "#ef4444",
};
const color = computed(() => JUDGMENT_COLORS[props.judgment]);
const gradientId = computed(() => `macro-grad-${Math.random().toString(36).slice(2, 9)}`);

// 取值域：纳入阈值线，确保高低位虚线可见
const domain = computed(() => {
  const values = props.points.map((p) => p.value);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (props.high != null) {
    min = Math.min(min, props.high);
    max = Math.max(max, props.high);
  }
  if (props.low != null) {
    min = Math.min(min, props.low);
    max = Math.max(max, props.low);
  }
  const pad = (max - min || 1) * 0.05;
  return { min: min - pad, max: max + pad };
});
const domainMin = computed(() => domain.value.min);
const domainMax = computed(() => domain.value.max);

function yOf(value: number): number {
  const { min, max } = domain.value;
  const range = max - min || 1;
  return PAD_Y + (1 - (value - min) / range) * (H - 2 * PAD_Y);
}

const coords = computed(() => {
  const n = props.points.length;
  return props.points.map((p, i) => ({
    x: n === 1 ? W / 2 : (i / (n - 1)) * W,
    y: yOf(p.value),
  }));
});

// 平滑曲线（Catmull-Rom 转贝塞尔）
const linePath = computed(() => {
  const pts = coords.value;
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`;
  }
  return d;
});
const areaPath = computed(() => {
  if (!linePath.value) return "";
  return `${linePath.value} L ${W},${H} L 0,${H} Z`;
});

const highY = computed(() => (props.high != null ? yOf(props.high) : null));
const lowY = computed(() => (props.low != null ? yOf(props.low) : null));

const hoverIndex = ref<number | null>(null);
function onMove(e: MouseEvent) {
  const n = props.points.length;
  if (n < 2) return;
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  hoverIndex.value = Math.round(frac * (n - 1));
}

function formatValue(v: number): string {
  return v.toLocaleString("en-US", {
    minimumFractionDigits: props.decimals,
    maximumFractionDigits: props.decimals,
  });
}
</script>
