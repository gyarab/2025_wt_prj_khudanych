<template>
  <footer class="footer">
    <div class="footer-inner">
      <span>© 2026 Just Enough Flags</span>
      <span class="separator" aria-hidden="true">·</span>
      <a href="/api/docs" target="_blank">API</a>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
}

.footer-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  max-width: 1280px;
  margin: 0 auto;
  padding: 1.25rem 1.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.separator { opacity: 0.4; }

a {
  color: var(--text-muted);
  text-decoration: none;
  transition: color var(--duration) var(--ease);
}
a:hover { color: var(--text-heading); }
</style>