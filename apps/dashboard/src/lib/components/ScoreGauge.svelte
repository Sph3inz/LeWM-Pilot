<script lang="ts">
  let { score = 0, band = 'moderate' }: { score?: number; band?: string } = $props();
  const pct = $derived(Math.round(score * 100));
</script>

<div class="gauge">
  <div class="track">
    <div class="fill band-{band}" style="width: {pct}%"></div>
  </div>
</div>

<style>
  .gauge {
    margin: 4px 0 8px;
    flex-shrink: 0;
  }

  .track {
    height: 6px;
    background: var(--bg-muted);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    border-radius: var(--radius-pill);
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .fill.band-excellent { background: #22c55e; }
  .fill.band-moderate { background: #3b82f6; }
  .fill.band-struggling { background: #f97316; }
</style>
