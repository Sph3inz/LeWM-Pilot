<script lang="ts">
  import type { TelemetryFrame } from '$lib/stores/telemetry';

  let { history = [] }: { history?: TelemetryFrame[] } = $props();

  const points = $derived.by(() => {
    const slice = history.slice(-60);
    if (slice.length < 2) return '';
    return slice
      .map((f, i) => {
        const x = (i / (slice.length - 1)) * 100;
        const y = 88 - f.pilot_score * 76;
        return `${x},${y}`;
      })
      .join(' ');
  });
</script>

<svg viewBox="0 0 100 100" preserveAspectRatio="none" class="chart" aria-hidden="true">
  {#if points}
    <polyline {points} class="line" />
  {/if}
</svg>

<style>
  .chart {
    width: 100%;
    height: 44px;
    margin-top: 2px;
    flex-shrink: 0;
  }

  .line {
    fill: none;
    stroke: var(--accent);
    stroke-width: 1.5;
    vector-effect: non-scaling-stroke;
    opacity: 0.85;
  }
</style>
