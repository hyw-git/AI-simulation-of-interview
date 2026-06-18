<template>
  <div class="radar-wrap">
    <svg :viewBox="`0 0 ${size} ${size}`" class="radar-svg" role="img" aria-label="评分维度雷达图">
      <g :transform="`translate(${center}, ${center})`">
        <polygon
          v-for="ring in rings"
          :key="`ring-${ring}`"
          :points="ringPoints(ring)"
          class="ring"
        />
        <line
          v-for="(axis, idx) in axes"
          :key="`axis-${idx}`"
          :x1="0"
          :y1="0"
          :x2="axis.x"
          :y2="axis.y"
          class="axis"
        />

        <polygon :points="valuePoints" class="value-fill" />
        <polyline :points="valueLinePoints" class="value-line" />
        <circle
          v-for="(p, idx) in valuePointArray"
          :key="`pt-${idx}`"
          :cx="p.x"
          :cy="p.y"
          r="2.5"
          class="value-dot"
        />

        <text
          v-for="(axis, idx) in axes"
          :key="`label-${idx}`"
          :x="axis.lx"
          :y="axis.ly"
          class="label"
          text-anchor="middle"
        >
          {{ axis.label }}
        </text>
      </g>
    </svg>

    <ul class="legend">
      <li v-for="(d, idx) in data" :key="`legend-${idx}`">
        <span>{{ d.label }}</span>
        <b>{{ d.value }}</b>
      </li>
    </ul>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'RadarChart',
  props: {
    data: {
      type: Array,
      default: () => []
    },
    size: {
      type: Number,
      default: 260
    }
  },
  setup(props) {
    const center = computed(() => props.size / 2)
    const radius = computed(() => props.size * 0.34)
    const rings = [0.2, 0.4, 0.6, 0.8, 1]

    const axes = computed(() => {
      const n = Math.max(3, props.data.length)
      return props.data.map((d, i) => {
        const ang = (-Math.PI / 2) + (i * Math.PI * 2) / n
        const x = Math.cos(ang) * radius.value
        const y = Math.sin(ang) * radius.value
        const lx = Math.cos(ang) * (radius.value + 16)
        const ly = Math.sin(ang) * (radius.value + 16)
        return { x, y, lx, ly, label: d.label }
      })
    })

    function ringPoints(scale) {
      return axes.value
        .map(a => `${a.x * scale},${a.y * scale}`)
        .join(' ')
    }

    const valuePointArray = computed(() => {
      return axes.value.map((a, idx) => {
        const v = Math.max(0, Math.min(100, Number(props.data[idx]?.value || 0))) / 100
        return { x: a.x * v, y: a.y * v }
      })
    })

    const valuePoints = computed(() => valuePointArray.value.map(p => `${p.x},${p.y}`).join(' '))
    const valueLinePoints = computed(() => {
      if (!valuePointArray.value.length) {
        return ''
      }
      const points = valuePointArray.value.map(p => `${p.x},${p.y}`)
      points.push(points[0])
      return points.join(' ')
    })

    return { center, rings, axes, ringPoints, valuePointArray, valuePoints, valueLinePoints }
  }
}
</script>

<style scoped>
.radar-wrap { display: grid; grid-template-columns: 1fr; gap: 10px; }
.radar-svg { width: 100%; max-width: 320px; margin: 0 auto; display: block; }
.ring { fill: none; stroke: rgba(82, 45, 125, 0.18); stroke-width: 1; }
.axis { stroke: rgba(82, 45, 125, 0.24); stroke-width: 1; }
.value-fill { fill: rgba(126, 75, 191, 0.22); }
.value-line { fill: none; stroke: #5d2f95; stroke-width: 2.2; }
.value-dot { fill: #5d2f95; }
.label { font-size: 10px; fill: #4e3c69; }
.legend { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.legend li { display: flex; justify-content: space-between; color: #4a3d63; font-size: 13px; }
.legend b { color: #3a235a; }
</style>
