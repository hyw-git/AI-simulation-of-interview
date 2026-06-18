<template>
  <div class="trend-wrap">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      class="trend-svg"
      role="img"
      aria-label="近期面试得分趋势图"
    >
      <defs>
        <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(31, 79, 185, 0.18)" />
          <stop offset="100%" stop-color="rgba(31, 79, 185, 0.02)" />
        </linearGradient>
      </defs>

      <g class="grid-group">
        <line
          v-for="tick in yTicks"
          :key="`grid-${tick}`"
          :x1="padLeft"
          :y1="yAt(tick)"
          :x2="width - padRight"
          :y2="yAt(tick)"
          class="grid-line"
        />
        <text
          v-for="tick in yTicks"
          :key="`ylabel-${tick}`"
          :x="padLeft - 6"
          :y="yAt(tick) + 3"
          class="axis-label y-label"
          text-anchor="end"
        >
          {{ tick }}
        </text>
      </g>

      <polygon v-if="areaPoints" :points="areaPoints" class="trend-area" />
      <polyline v-if="plotPoints.length > 1" :points="linePoints" class="trend-line" />

      <g v-for="(p, idx) in plotPoints" :key="`pt-${idx}`">
        <circle :cx="p.x" :cy="p.y" r="3.5" class="trend-dot" />
        <text
          v-if="showXLabel(idx)"
          :x="p.x"
          :y="height - padBottom + 14"
          class="axis-label x-label"
          text-anchor="middle"
        >
          {{ p.shortLabel }}
        </text>
        <title>{{ p.fullLabel }} · {{ p.value }} 分</title>
      </g>
    </svg>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'ScoreTrendChart',
  props: {
    points: {
      type: Array,
      default: () => []
    },
    width: { type: Number, default: 480 },
    height: { type: Number, default: 148 },
    showLegend: { type: Boolean, default: false }
  },
  setup(props) {
    const padLeft = 30
    const padRight = 10
    const padTop = 10
    const padBottom = 22
    const yTicks = [0, 50, 100]

    const plotPoints = computed(() => {
      const pts = props.points || []
      if (!pts.length) return []
      const innerW = props.width - padLeft - padRight
      const innerH = props.height - padTop - padBottom
      const step = pts.length > 1 ? innerW / (pts.length - 1) : 0

      return pts.map((p, idx) => {
        const val = Math.max(0, Math.min(100, Number(p.value) || 0))
        const x = padLeft + (pts.length > 1 ? idx * step : innerW / 2)
        const y = padTop + innerH * (1 - val / 100)
        return {
          x,
          y,
          value: val,
          shortLabel: p.shortLabel || '',
          fullLabel: p.fullLabel || p.shortLabel || ''
        }
      })
    })

    const linePoints = computed(() =>
      plotPoints.value.map(p => `${p.x},${p.y}`).join(' ')
    )

    const areaPoints = computed(() => {
      const pts = plotPoints.value
      if (!pts.length) return ''
      const baseY = padTop + (props.height - padTop - padBottom)
      const top = pts.map(p => `${p.x},${p.y}`).join(' ')
      const close = `${pts[pts.length - 1].x},${baseY} ${pts[0].x},${baseY}`
      return `${top} ${close}`
    })

    function yAt(tick) {
      const innerH = props.height - padTop - padBottom
      return padTop + innerH * (1 - tick / 100)
    }

    function showXLabel(idx) {
      const n = plotPoints.value.length
      if (n <= 6) return true
      if (n <= 10) return idx % 2 === 0 || idx === n - 1
      return idx % 3 === 0 || idx === n - 1
    }

    return {
      padLeft,
      padRight,
      padBottom,
      yTicks,
      plotPoints,
      linePoints,
      areaPoints,
      yAt,
      showXLabel
    }
  }
}
</script>

<style scoped>
.trend-wrap {
  max-width: 640px;
}
.trend-svg {
  width: 100%;
  max-height: 148px;
  display: block;
}
.grid-line {
  stroke: rgba(37, 89, 214, 0.1);
  stroke-width: 1;
}
.axis-label {
  font-size: 9px;
  fill: #8a9bb5;
  font-family: inherit;
}
.y-label {
  font-size: 8px;
}
.x-label {
  font-size: 8px;
}
.trend-area {
  fill: url(#trendFill);
}
.trend-line {
  fill: none;
  stroke: #3b6fd4;
  stroke-width: 1.8;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.trend-dot {
  fill: #fff;
  stroke: #3b6fd4;
  stroke-width: 1.8;
}

:global([data-theme="dark"]) .axis-label {
  fill: rgba(203, 213, 225, 0.65);
}
:global([data-theme="dark"]) .grid-line {
  stroke: rgba(122, 162, 255, 0.12);
}
:global([data-theme="dark"]) .trend-line {
  stroke: #6b9fff;
}
:global([data-theme="dark"]) .trend-dot {
  fill: #121a26;
  stroke: #6b9fff;
}
</style>
