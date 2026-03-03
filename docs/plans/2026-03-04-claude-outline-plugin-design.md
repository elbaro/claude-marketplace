# claude-outline Plugin Design

## Overview

Claude Code plugin that replaces the existing Outline MCP server with a single skill + Python CLI wrapper, providing full Outline API access with better response filtering and token efficiency.

## Directory Structure

```
claude-outline/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── outline/
│       ├── SKILL.md
│       └── scripts/
│           └── outline_api.py
├── README.md
└── LICENSE
```

## Components

### plugin.json

Standard Claude Code plugin metadata. Name: `claude-outline`.

### SKILL.md

- **Trigger**: User asks to interact with Outline wiki (documents, collections, comments)
- **Content**: API endpoint quick reference table + outline_api.py usage
- **Target length**: <200 lines

### outline_api.py

Generic CLI wrapper for Outline REST API.

**Usage**: `python3 outline_api.py <endpoint> [--param=value ...]`

**Environment variables**:
- `OUTLINE_API_KEY` (required) — Bearer token
- `OUTLINE_API_URL` (required) — API base URL (e.g., `https://outline.internal/api`)
- `OUTLINE_SSL_VERIFY` (optional, default `true`) — Set `false` for self-signed certs

**Features**:
- Generic handler: passes all `--param=value` args directly to the API endpoint
- Response filtering: compact output by default (id+title+text for docs, id+title for lists)
- `--raw` flag for full JSON response
- `--text-file=path` to read text content from file (for document updates)
- Proper error handling with HTTP status codes

**Covered endpoints** (20):

| Category | Endpoints |
|---|---|
| Documents (12) | info, list, search, search_titles, create, update, delete, move, archive, restore, duplicate, documents |
| Collections (6) | info, list, create, update, delete, documents |
| Comments (2) | create, list |

**Response filtering strategy**:
- `documents.info` → id, title, text (drop createdBy, policies, data, etc.)
- `documents.list` → [{id, title, updatedAt}]
- `documents.search` → [{id, title, context}]
- `documents.search_titles` → [{id, title}]
- `collections.documents` → tree of {id, title, children}
- `--raw` bypasses all filtering

## Compatibility

Uses same env vars as existing MCP server (`OUTLINE_API_KEY`, `OUTLINE_API_URL`). MCP server can be removed after plugin installation.
