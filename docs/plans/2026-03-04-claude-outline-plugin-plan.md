# claude-outline Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Claude Code plugin that provides Outline wiki API access via a single skill + Python CLI wrapper.

**Architecture:** One skill (`outline`) with a SKILL.md reference and `outline_api.py` CLI. The Python script handles auth, SSL, request dispatch, and response filtering. SKILL.md provides the API quick reference so Claude knows which endpoints and parameters are available.

**Tech Stack:** Python 3 (stdlib only: urllib, json, ssl, sys, os), Claude Code plugin format

---

### Task 1: Plugin boilerplate

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `LICENSE`

**Step 1: Create plugin.json**

```json
{
  "name": "claude-outline",
  "description": "Outline wiki integration for Claude Code — documents, collections, comments via REST API",
  "version": "0.1.0",
  "author": {
    "name": "emppu"
  },
  "license": "MIT"
}
```

**Step 2: Create MIT LICENSE file**

Standard MIT license with year 2026.

**Step 3: Commit**

```bash
git add .claude-plugin/plugin.json LICENSE
git commit -m "feat: add plugin boilerplate"
```

---

### Task 2: Write outline_api.py

**Files:**
- Create: `skills/outline/scripts/outline_api.py`

**Step 1: Implement the CLI wrapper**

The script must:

1. **Parse args**: `<endpoint>` as first positional arg, `--key=value` for API params, `--raw` for unfiltered output, `--text-file=path` to read `text` param from file
2. **Auth**: Read `OUTLINE_API_KEY` and `OUTLINE_API_URL` from env. Error clearly if missing.
3. **SSL**: If `OUTLINE_SSL_VERIFY=false`, disable cert verification.
4. **Request**: POST to `{API_URL}/{endpoint}` with JSON body from parsed params. Type coercion: `"true"`/`"false"` → bool, numeric strings → int.
5. **Response filtering**: By default, apply endpoint-specific compact filters. `--raw` outputs full JSON.

Response filters (compact mode):

| Endpoint | Output fields |
|---|---|
| `documents.info` | `{id, title, text}` |
| `documents.list` | `[{id, title, updatedAt}]` |
| `documents.search` | `[{ranking, context, document: {id, title}}]` |
| `documents.search_titles` | `[{id, title}]` |
| `documents.create` | `{id, title, url}` |
| `documents.update` | `{id, title, revision}` |
| `documents.delete` | `{success}` |
| `documents.move` | `{id, title, collectionId}` from `data.documents[0]` |
| `documents.archive` | `{id, title}` |
| `documents.restore` | `{id, title}` |
| `documents.duplicate` | `[{id, title, url}]` from `data.documents` |
| `documents.documents` | recursive `[{id, title, children}]` from `data` |
| `collections.info` | `{id, name, description}` |
| `collections.list` | `[{id, name}]` |
| `collections.create` | `{id, name, url}` |
| `collections.update` | `{id, name}` |
| `collections.delete` | `{success}` |
| `collections.documents` | recursive `[{id, title, children}]` from `data` |
| `comments.create` | `{id, documentId, createdAt}` |
| `comments.list` | `[{id, createdBy: {name}, text, createdAt}]` |
| (unknown endpoint) | pass through `data` as-is |

**Step 2: Verify script runs**

```bash
python3 skills/outline/scripts/outline_api.py --help
# Should print usage
python3 skills/outline/scripts/outline_api.py documents.search_titles --query="스타트업"
# Should return compact results
```

**Step 3: Commit**

```bash
git add skills/outline/scripts/outline_api.py
git commit -m "feat: add outline_api.py CLI wrapper"
```

---

### Task 3: Write SKILL.md

**Files:**
- Create: `skills/outline/SKILL.md`

**Step 1: Write the skill**

Structure:
- Frontmatter: `name: outline`, description with "Use when" trigger
- Overview: 2 sentences
- Usage: How to invoke outline_api.py with `${CLAUDE_PLUGIN_ROOT}`
- Quick Reference: Table of all 20 endpoints with required params and description
- Response Filtering: Brief note about compact vs --raw
- Environment Setup: Required env vars

Target: <200 lines, <500 words. This is a Reference-type skill.

Key principle: description must only describe WHEN to use, not HOW it works.

```yaml
---
name: outline
description: Use when reading, searching, creating, updating, or organizing documents and collections in Outline wiki, or managing Outline comments
---
```

**Step 2: Verify word count**

```bash
wc -w skills/outline/SKILL.md
# Target: <500 words
```

**Step 3: Commit**

```bash
git add skills/outline/SKILL.md
git commit -m "feat: add outline skill with API reference"
```

---

### Task 4: Integration test

**Step 1: Test document read**

```bash
cd ~/repo/claude-outline
OUTLINE_API_KEY="$OUTLINE_API_KEY" OUTLINE_API_URL="$OUTLINE_API_URL" \
  python3 skills/outline/scripts/outline_api.py documents.search_titles --query="스타트업" --limit=2
```

Expected: Compact JSON with id and title fields.

**Step 2: Test collection tree**

```bash
OUTLINE_API_KEY="$OUTLINE_API_KEY" OUTLINE_API_URL="$OUTLINE_API_URL" \
  python3 skills/outline/scripts/outline_api.py collections.list
```

Expected: List of `{id, name}`.

**Step 3: Test raw mode**

```bash
OUTLINE_API_KEY="$OUTLINE_API_KEY" OUTLINE_API_URL="$OUTLINE_API_URL" \
  python3 skills/outline/scripts/outline_api.py documents.search_titles --query="test" --limit=1 --raw
```

Expected: Full JSON response with all fields.

**Step 4: Test error handling**

```bash
python3 skills/outline/scripts/outline_api.py documents.info --id=nonexistent
```

Expected: Clear error message with HTTP status.

**Step 5: Fix any issues found, commit if changes made**

---

### Task 5: Final commit and summary

**Step 1: Verify directory structure**

```bash
find . -type f | grep -v .git | sort
```

Expected:
```
./.claude-plugin/plugin.json
./LICENSE
./docs/plans/2026-03-04-claude-outline-plugin-design.md
./docs/plans/2026-03-04-claude-outline-plugin-plan.md
./skills/outline/SKILL.md
./skills/outline/scripts/outline_api.py
```

**Step 2: Final commit if any unstaged changes remain**
