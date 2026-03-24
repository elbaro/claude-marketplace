# Claude Marketplace

Custom Claude Code plugin marketplace.

## Release Checklist

When bumping a plugin version, update BOTH files:

1. `plugins/<plugin-name>/.claude-plugin/plugin.json` — plugin's own version
2. `.claude-plugin/marketplace.json` — marketplace registry version

These must stay in sync. Claude Code reads `marketplace.json` for discovery/installation and `plugin.json` after loading.
