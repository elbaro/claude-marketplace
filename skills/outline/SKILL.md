---
name: outline
description: Use when reading, searching, creating, updating, or organizing documents and collections in Outline wiki, or managing Outline comments
---

# Outline API

CLI wrapper for Outline wiki REST API. Compact output by default for token efficiency.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/outline/scripts/outline_api.py <endpoint> [--param=value ...] [--raw] [--text-file=path]
```

- `--raw` — full JSON response (skip filtering)
- `--text-file=path` — read `text` param from file (for document updates with long content)

## Quick Reference

### Documents

| Endpoint | Required params | Description |
|---|---|---|
| `documents.info` | `--id` | Get document (returns id, title, text) |
| `documents.list` | | List documents. `--collectionId`, `--limit`, `--offset` |
| `documents.search` | `--query` | Full-text search. `--collectionId`, `--limit` |
| `documents.search_titles` | `--query` | Title-only search (lightweight) |
| `documents.create` | `--title` `--collectionId` | Create document. `--text`, `--parentDocumentId`, `--publish` |
| `documents.update` | `--id` | Update document. `--title`, `--text`, `--text-file` |
| `documents.delete` | `--id` | Trash document. `--permanent=true` for hard delete |
| `documents.move` | `--id` | Move document. `--collectionId`, `--parentDocumentId` |
| `documents.archive` | `--id` | Archive document |
| `documents.restore` | `--id` | Restore archived/trashed document |
| `documents.duplicate` | `--id` | Clone document. `--recursive=true` for children |
| `documents.documents` | `--id` | Get child document tree (NavigationNode) |

### Collections

| Endpoint | Required params | Description |
|---|---|---|
| `collections.info` | `--id` | Get collection details |
| `collections.list` | | List all collections |
| `collections.create` | `--name` | Create collection. `--description`, `--permission` |
| `collections.update` | `--id` | Update collection. `--name`, `--description` |
| `collections.delete` | `--id` | Delete collection |
| `collections.documents` | `--id` | Get document tree for collection |

### Comments

| Endpoint | Required params | Description |
|---|---|---|
| `comments.create` | `--documentId` `--text` | Add comment. `--parentCommentId` for replies |
| `comments.list` | | List comments. `--documentId`, `--collectionId`, `--limit` |

## Compact Output

Default output strips metadata for token savings. Use `--raw` for full response.

| Endpoint | Compact fields |
|---|---|
| `documents.info` | id, title, text |
| `documents.list` | id, title, updatedAt |
| `documents.search` | ranking, context, document.id, document.title |
| `collections.list` | id, name |
| Tree endpoints | id, title, url, children (recursive) |

## Environment

Required in `~/.claude/settings.json` → `env`:

```json
{
  "OUTLINE_API_KEY": "ol_api_...",
  "OUTLINE_API_URL": "https://your-outline.example/api",
  "OUTLINE_SSL_VERIFY": "false"
}
```

`OUTLINE_SSL_VERIFY=false` disables cert verification for self-hosted instances.
