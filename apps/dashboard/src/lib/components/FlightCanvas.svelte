<script lang="ts">
  import type { TelemetryFrame } from '$lib/stores/telemetry';

  let {
    history = [],
    heading = 0,
    altFt = 0,
    iasKt = 0,
    failures = []
  }: {
    history?: TelemetryFrame[];
    heading?: number;
    altFt?: number;
    iasKt?: number;
    failures?: string[];
  } = $props();

  const cx = 150;
  const cy = 130;
  const scale = 0.035;

  const trailPoints = $derived.by(() => {
    const slice = history.slice(-120);
    if (slice.length === 0) return [{ x: cx, y: cy }];

    const xs = slice.map((f) => f.position.x_m);
    const ys = slice.map((f) => f.position.y_m);
    const hasMotion = Math.max(...xs) - Math.min(...xs) > 1 || Math.max(...ys) - Math.min(...ys) > 1;

    if (hasMotion) {
      return slice.map((f) => ({
        x: cx + f.position.x_m * scale,
        y: cy - f.position.y_m * scale
      }));
    }

    // Fallback: trace heading drift when sim position stays at origin
    return slice.map((f, i) => {
      const rad = (f.heading_deg * Math.PI) / 180;
      const r = 18 + i * 0.35;
      return {
        x: cx + Math.sin(rad) * r,
        y: cy - Math.cos(rad) * r
      };
    });
  });

  const trailPath = $derived(
    trailPoints.length > 1
      ? trailPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
      : ''
  );

  const lastPoint = $derived(trailPoints[trailPoints.length - 1] ?? { x: cx, y: cy });
</script>

<div class="wrap">
  <svg viewBox="0 0 300 260" class="canvas" role="img" aria-label="Flight trace">
    <defs>
      <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
        <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#ebebeb" stroke-width="0.75" />
      </pattern>
    </defs>
    <rect width="300" height="260" fill="url(#grid)" />
    <rect width="300" height="260" fill="#fafafa" opacity="0.85" />

    <!-- compass ring -->
    <circle cx={cx} cy={cy} r="72" fill="none" stroke="#e4e4e7" stroke-width="1" />
    <text x={cx} y={cy - 78} text-anchor="middle" class="compass-label">N</text>

    {#if trailPath}
      <path d={trailPath} fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" opacity="0.7" />
    {:else}
      <text x={cx} y={cy + 4} text-anchor="middle" class="empty-hint">Awaiting trail data…</text>
    {/if}

    <!-- aircraft: wings-level symbol (not play-button triangle) -->
    <g transform="translate({lastPoint.x},{lastPoint.y}) rotate({-heading})">
      <line x1="-14" y1="0" x2="14" y2="0" stroke="#18181b" stroke-width="2.5" stroke-linecap="round" />
      <line x1="0" y1="0" x2="0" y2="-12" stroke="#18181b" stroke-width="2" stroke-linecap="round" />
      <circle cx="0" cy="0" r="3" fill="#2563eb" />
    </g>
  </svg>

  <div class="hud">
    <div><span class="hud-k">HDG</span> {heading.toFixed(0)}°</div>
    <div><span class="hud-k">ALT</span> {altFt.toFixed(0)} ft</div>
    <div><span class="hud-k">IAS</span> {iasKt.toFixed(0)} kt</div>
  </div>

  {#if failures.length}
    <div class="tags">
      {#each failures as f}
        <span>{f.replace(/_/g, ' ')}</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    flex: 1;
    min-height: 120px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: #fafafa;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .canvas {
    width: 100%;
    height: 100%;
    min-height: 120px;
    max-height: 100%;
    display: block;
    object-fit: contain;
  }

  .compass-label {
    font-size: 10px;
    fill: var(--text-muted);
    font-family: var(--font);
  }

  .empty-hint {
    font-size: 11px;
    fill: var(--text-muted);
    font-family: var(--font);
  }

  .hud {
    position: absolute;
    bottom: 14px;
    left: 14px;
    display: flex;
    gap: 14px;
    padding: 7px 12px;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid var(--border-subtle);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .hud-k {
    color: var(--text-muted);
    font-weight: 600;
    margin-right: 3px;
  }

  .tags {
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: flex-end;
  }

  .tags span {
    font-size: 10px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: var(--radius-pill);
    background: var(--danger-soft);
    color: #b91c1c;
    text-transform: capitalize;
  }
</style>
