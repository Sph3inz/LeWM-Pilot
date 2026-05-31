<script lang="ts">
  import type { AdaptationLogEntry } from '$lib/stores/telemetry';

  let { entries = [] }: { entries?: AdaptationLogEntry[] } = $props();

  const recent = $derived([...entries].reverse().slice(0, 8));
</script>

<div class="log">
  {#if recent.length === 0}
    <p class="empty">Profiler and planner events will appear here.</p>
  {:else}
    {#each recent as entry}
      <div class="row">
        <span class="time mono">{entry.sim_time_s.toFixed(1)}s</span>
        <span class="source">{entry.source}</span>
        <span class="msg">{entry.message}</span>
      </div>
    {/each}
  {/if}
</div>

<style>
  .log {
    overflow-y: auto;
    flex: 1;
    min-height: 0;
    max-height: 100%;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
  }

  .empty {
    margin: 0;
    padding: 12px 0;
    font-size: 12px;
    color: var(--text-muted);
  }

  .row {
    display: grid;
    grid-template-columns: 44px 52px 1fr;
    gap: 8px;
    padding: 9px 2px;
    border-bottom: 1px solid var(--border-subtle);
    align-items: start;
  }

  .row:last-child {
    border-bottom: none;
  }

  .time {
    font-size: 10px;
    color: var(--text-muted);
    padding-top: 1px;
  }

  .source {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
  }

  .msg {
    font-size: 12px;
    line-height: 1.4;
    color: var(--text);
  }
</style>
