---
name: outline
description: Use when reading, searching, creating, updating, or organizing documents and collections in Outline wiki, managing Outline comments, or uploading/downloading file attachments
---

# Outline API

CLI wrapper for Outline wiki REST API. Compact output by default for token efficiency.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/outline/scripts/outline_api.py <command> [--param=value ...] [--raw] [--text-file=path]
```

`--raw` returns full JSON. `--text-file=path` reads `text` param from file. `--old-file`/`--new-file` for replace with special chars. `--description-file=path` reads `description` param from file.

## High-Level Commands

Fetch→modify→update internally. Text never enters context. All text commands accept **--id** (document) or **--collectionId** (collection description).

<commands type="high-level">
<cmd name="replace" required="--id|--collectionId --old --new">String replace in document or collection description. Use --old-file/--new-file for text with quotes or newlines</cmd>
<cmd name="append" required="--id|--collectionId --text">Append to end of document or collection description. Supports --text-file</cmd>
<cmd name="prepend" required="--id|--collectionId --text">Insert after first heading. Supports --text-file</cmd>
<cmd name="section-read" required="--id|--collectionId --heading">Read one section by heading substring</cmd>
<cmd name="section-delete" required="--id|--collectionId --heading">Delete section by heading substring</cmd>
<cmd name="upload" required="--file --documentId" optional="--name">Upload file attachment (2-step). Returns attachment markdown link</cmd>
<cmd name="download" required="--id --output">Download attachment to local file</cmd>
</commands>

## API Endpoints

<commands type="documents">
<cmd name="documents.info" required="--id">Get document (compact: id, title, text)</cmd>
<cmd name="documents.list" optional="--collectionId --limit --offset">List documents (compact: id, title, updatedAt)</cmd>
<cmd name="documents.search" required="--query" optional="--collectionId --limit">Full-text search (compact: ranking, context, document.id/title)</cmd>
<cmd name="documents.search_titles" required="--query" optional="--collectionId --limit">Title-only search (lightweight)</cmd>
<cmd name="documents.create" required="--title --collectionId" optional="--text --parentDocumentId --publish --text-file">Create document</cmd>
<cmd name="documents.update" required="--id" optional="--title --text --text-file">Update document</cmd>
<cmd name="documents.delete" required="--id" optional="--permanent=true">Trash (or hard delete)</cmd>
<cmd name="documents.move" required="--id" optional="--collectionId --parentDocumentId">Move document</cmd>
<cmd name="documents.archive" required="--id">Archive</cmd>
<cmd name="documents.restore" required="--id">Restore archived/trashed</cmd>
<cmd name="documents.duplicate" required="--id" optional="--recursive=true">Clone document</cmd>
<cmd name="documents.documents" required="--id">Child document tree (compact: id, title, url, children)</cmd>
</commands>

<commands type="collections">
<cmd name="collections.info" required="--id">Get collection details</cmd>
<cmd name="collections.list">List all collections (compact: id, name)</cmd>
<cmd name="collections.create" required="--name" optional="--description --permission">Create collection</cmd>
<cmd name="collections.update" required="--id" optional="--name --description --description-file">Update collection</cmd>
<cmd name="collections.delete" required="--id">Delete collection</cmd>
<cmd name="collections.documents" required="--id">Document tree (compact: id, title, url, children)</cmd>
</commands>

<commands type="comments">
<cmd name="comments.create" required="--documentId --text" optional="--parentCommentId">Add comment</cmd>
<cmd name="comments.list" optional="--documentId --collectionId --limit">List comments</cmd>
</commands>

<commands type="attachments">
<cmd name="attachments.delete" required="--id">Delete an attachment</cmd>
</commands>

## Environment

Set in `~/.claude/settings.json` → `env`:
- `OUTLINE_API_KEY` (required): API token
- `OUTLINE_API_URL` (required): Base URL, e.g. `https://outline.example/api`
- `OUTLINE_SSL_VERIFY`: Set `false` for self-signed certs
