<script lang="ts">
  import { plannerBackend, plannerDevice } from '$lib/stores/telemetry';

  const label = $derived(
    $plannerBackend === 'lewm'
      ? 'Real LeWM'
      : $plannerBackend === 'mock'
        ? 'Mock LeWM'
        : 'Unknown'
  );

  const detail = $derived(
    $plannerBackend === 'lewm' && $plannerDevice ? $plannerDevice : null
  );
</script>

<span class="badge" class:lewm={$plannerBackend === 'lewm'} class:mock={$plannerBackend === 'mock'}>
  <span class="badge-dot"></span>
  {label}{#if detail}<span class="device mono"> · {detail}</span>{/if}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
  }

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-muted);
    flex-shrink: 0;
  }

  .badge.lewm {
    color: #1d4ed8;
  }

  .badge.lewm .badge-dot {
    background: #2563eb;
  }

  .badge.mock {
    color: #c2410c;
  }

  .badge.mock .badge-dot {
    background: var(--accent-orange);
  }

  .device {
    font-weight: 400;
    color: var(--text-muted);
  }
</style>
