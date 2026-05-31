<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { connectWebSocket, connectionState, fetchServerHealth, latestFrame } from '$lib/stores/telemetry';
  import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';
  import PlannerStatus from '$lib/components/PlannerStatus.svelte';
  import VibePromptChat from '$lib/components/VibePromptChat.svelte';

  onMount(() => {
    void fetchServerHealth();
    connectWebSocket();
  });
</script>

<div class="shell">
  <aside class="sidebar">
    <div class="sidebar-header">
      <button class="sidebar-btn" type="button">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
        New session
      </button>
    </div>

    <div class="tree">
      <div class="tree-label">Workspaces</div>
      <div class="tree-folder">SkyMind</div>
      <button class="tree-item active" type="button">
        <span class="tree-dot"></span>
        Live session
      </button>
      <button class="tree-item" type="button">
        <span class="tree-dot muted"></span>
        Scenario compiler
      </button>
    </div>

    <div class="sidebar-status">
      <div class="status-line">
        <span>Connection</span>
        <ConnectionStatus />
      </div>
      <div class="status-line">
        <span>Planner</span>
        <PlannerStatus />
      </div>
      {#if $latestFrame}
        <div class="status-line">
          <span>Aircraft</span>
          <code class="mono">{$latestFrame.aircraft_id.toUpperCase()}</code>
        </div>
        <div class="status-line">
          <span>Sim time</span>
          <code class="mono">{$latestFrame.sim_time_s.toFixed(1)}s</code>
        </div>
        <div class="status-line">
          <span>Heading</span>
          <code class="mono">{$latestFrame.heading_deg.toFixed(0)}°</code>
        </div>
      {/if}
    </div>

    <div class="sidebar-user">
      <div class="avatar">SM</div>
      <div>
        <div class="user-name">SkyMind Demo</div>
        <div class="user-meta">Phase 1 · JSBSim</div>
      </div>
    </div>
  </aside>

  <div class="main">
    <header class="doc-header">
      <div class="doc-tab">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
        Live adaptive session
      </div>
    </header>

    <div class="doc-body">
      <slot />
    </div>

    <footer class="composer-area">
      <VibePromptChat />
      <div class="composer-status">
        <ConnectionStatus />
        <span class="status-text muted">
          {$connectionState === 'open' ? 'Streaming · 20 Hz' : 'Reconnecting…'}
        </span>
      </div>
    </footer>
  </div>
</div>

<style>
  .shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
    background: var(--bg-app);
  }

  .sidebar {
    width: var(--sidebar-width);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-subtle);
    padding: 14px 12px;
  }

  .sidebar-header {
    padding: 0 6px 10px;
  }

  .sidebar-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 10px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    text-align: left;
  }

  .sidebar-btn:hover {
    background: rgba(0, 0, 0, 0.05);
    color: var(--text);
  }

  .tree {
    flex: 1;
    overflow-y: auto;
    padding: 0 4px;
  }

  .tree-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 10px 8px 6px;
  }

  .tree-folder {
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
    padding: 2px 8px 4px;
  }

  .tree-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 7px 10px 7px 18px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    text-align: left;
  }

  .tree-item:hover {
    background: rgba(0, 0, 0, 0.04);
    color: var(--text);
  }

  .tree-item.active {
    background: #e8e8ea;
    color: var(--text);
    font-weight: 500;
  }

  .tree-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent-orange);
    flex-shrink: 0;
  }

  .tree-dot.muted {
    background: #d4d4d8;
  }

  .sidebar-status {
    padding: 12px;
    margin: 8px 4px;
    border-radius: var(--radius-md);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
  }

  .status-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 4px 0;
    font-size: 11px;
    color: var(--text-muted);
  }

  .status-line code {
    font-size: 11px;
    color: var(--text);
    font-weight: 500;
  }

  .sidebar-user {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 8px 4px;
    margin-top: auto;
    border-top: 1px solid var(--border-subtle);
  }

  .avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #e4e4e7;
    color: var(--text-secondary);
    display: grid;
    place-items: center;
    font-size: 10px;
    font-weight: 700;
  }

  .user-name {
    font-size: 12px;
    font-weight: 600;
  }

  .user-meta {
    font-size: 11px;
    color: var(--text-muted);
  }

  .main {
    flex: 1;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
  }

  .doc-header {
    flex-shrink: 0;
    padding: 12px 24px 0;
    border-bottom: 1px solid var(--border-subtle);
  }

  .doc-tab {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 2px 11px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    border-bottom: 2px solid var(--text);
    margin-bottom: -1px;
  }

  .doc-body {
    min-height: 0;
    overflow: hidden;
    padding: 16px 24px 12px;
    display: flex;
    flex-direction: column;
  }

  .composer-area {
    padding: 10px 24px 14px;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-app);
    z-index: 2;
  }

  .composer-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
    padding: 0 4px;
  }

  .status-text.muted {
    font-size: 11px;
    color: var(--text-muted);
  }
</style>
