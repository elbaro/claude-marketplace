#!/usr/bin/env python3
"""CLI wrapper for the Outline wiki REST API.

Usage:
    python3 outline_api.py <endpoint> [--key=value ...] [--raw] [--text-file=path]

API endpoints:
    python3 outline_api.py documents.info --id=abc123
    python3 outline_api.py documents.search_titles --query="term" --limit=5
    python3 outline_api.py documents.update --id=abc123 --text-file=draft.md
    python3 outline_api.py collections.list --raw

High-level commands (fetch-modify-update internally, document text never enters context):
    python3 outline_api.py replace --id=abc123 --old="old text" --new="new text"
    python3 outline_api.py append --id=abc123 --text="new content"
    python3 outline_api.py prepend --id=abc123 --text="new content"
    python3 outline_api.py section-read --id=abc123 --heading="Section Name"
    python3 outline_api.py section-delete --id=abc123 --heading="Section Name"

Attachment commands:
    python3 outline_api.py upload --file=/path/to/file --documentId=<doc-id> [--name=display_name]
    python3 outline_api.py download --id=<attachment-id> --output=/path/to/save

Environment variables:
    OUTLINE_API_KEY      API token for authentication (required)
    OUTLINE_API_URL      Base URL of the Outline instance (required)
    OUTLINE_SSL_VERIFY   Set to "false" to disable SSL verification (optional)
"""

import json
import mimetypes
import os
import ssl
import sys
import uuid
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# High-level commands (fetch → modify → update internally)
# ---------------------------------------------------------------------------

HIGH_LEVEL_COMMANDS = {"replace", "append", "prepend", "section-read", "section-delete",
                       "upload", "download"}


def _get_doc_text(base_url, api_key, doc_id, verify_ssl):
    """Fetch document markdown text."""
    resp = api_request(base_url, api_key, "documents.info", {"id": doc_id}, verify_ssl)
    return resp["data"]["text"]


def _update_doc_text(base_url, api_key, doc_id, text, verify_ssl):
    """Update document text, return compact result."""
    resp = api_request(base_url, api_key, "documents.update",
                       {"id": doc_id, "text": text}, verify_ssl)
    return _pick(resp["data"], ("id", "title", "revision"))


def _find_section(text, heading):
    """Find markdown section by heading substring.

    Returns (start_line, end_line) or None. Respects code blocks.
    Section = from heading line to next heading of same or higher level.
    """
    lines = text.split("\n")
    in_code_block = False
    start_idx = None
    heading_level = 0

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        stripped = line.lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped.lstrip("#").strip()
            if start_idx is None:
                if heading in title:
                    start_idx = i
                    heading_level = level
            else:
                if level <= heading_level:
                    return start_idx, i

    if start_idx is not None:
        return start_idx, len(lines)
    return None


def cmd_replace(base_url, api_key, params, verify_ssl):
    """Replace text in a document. Supports --old/--new or --old-file/--new-file."""
    doc_id = params.get("id")
    old = params.get("old")
    new = params.get("new", "")

    if not doc_id or old is None:
        print("replace requires --id and --old (or --old-file)", file=sys.stderr)
        sys.exit(1)

    text = _get_doc_text(base_url, api_key, doc_id, verify_ssl)
    count = text.count(old)
    if count == 0:
        print(json.dumps({"error": "no match found", "query": old[:200]},
                          ensure_ascii=False, indent=2))
        sys.exit(1)

    new_text = text.replace(old, new)
    result = _update_doc_text(base_url, api_key, doc_id, new_text, verify_ssl)
    result["replacements"] = count
    return result


def cmd_append(base_url, api_key, params, verify_ssl):
    """Append text to end of document."""
    doc_id = params.get("id")
    new_content = params.get("text", "")
    if not doc_id or not new_content:
        print("append requires --id and --text (or --text-file)", file=sys.stderr)
        sys.exit(1)

    text = _get_doc_text(base_url, api_key, doc_id, verify_ssl)
    text = text.rstrip("\n") + "\n\n" + new_content + "\n"
    return _update_doc_text(base_url, api_key, doc_id, text, verify_ssl)


def cmd_prepend(base_url, api_key, params, verify_ssl):
    """Prepend text after the first heading (or at top if no heading)."""
    doc_id = params.get("id")
    new_content = params.get("text", "")
    if not doc_id or not new_content:
        print("prepend requires --id and --text (or --text-file)", file=sys.stderr)
        sys.exit(1)

    text = _get_doc_text(base_url, api_key, doc_id, verify_ssl)
    lines = text.split("\n")

    # Insert after first heading line, or at top
    insert_at = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            insert_at = i + 1
            break

    lines.insert(insert_at, "\n" + new_content + "\n")
    return _update_doc_text(base_url, api_key, doc_id, "\n".join(lines), verify_ssl)


def cmd_section_read(base_url, api_key, params, verify_ssl):
    """Read a single section by heading (substring match)."""
    doc_id = params.get("id")
    heading = params.get("heading")
    if not doc_id or not heading:
        print("section-read requires --id and --heading", file=sys.stderr)
        sys.exit(1)

    text = _get_doc_text(base_url, api_key, doc_id, verify_ssl)
    result = _find_section(text, heading)
    if result is None:
        print(json.dumps({"error": "section not found", "heading": heading},
                          ensure_ascii=False, indent=2))
        sys.exit(1)

    start, end = result
    section = "\n".join(text.split("\n")[start:end]).strip()
    return {"section": section}


def cmd_section_delete(base_url, api_key, params, verify_ssl):
    """Delete a section by heading (substring match)."""
    doc_id = params.get("id")
    heading = params.get("heading")
    if not doc_id or not heading:
        print("section-delete requires --id and --heading", file=sys.stderr)
        sys.exit(1)

    text = _get_doc_text(base_url, api_key, doc_id, verify_ssl)
    result = _find_section(text, heading)
    if result is None:
        print(json.dumps({"error": "section not found", "heading": heading},
                          ensure_ascii=False, indent=2))
        sys.exit(1)

    start, end = result
    lines = text.split("\n")
    deleted_heading = lines[start].lstrip("#").strip()
    new_lines = lines[:start] + lines[end:]
    new_text = "\n".join(new_lines)

    # Clean up triple+ blank lines
    while "\n\n\n" in new_text:
        new_text = new_text.replace("\n\n\n", "\n\n")

    update_result = _update_doc_text(base_url, api_key, doc_id, new_text, verify_ssl)
    update_result["deleted"] = deleted_heading
    return update_result


def _build_multipart(fields, file_field, file_path, file_content_type):
    """Build a multipart/form-data body from fields dict and a file.

    Returns (body_bytes, content_type_header).
    """
    boundary = uuid.uuid4().hex
    lines = []

    for key, value in fields.items():
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        lines.append(b"")
        lines.append(str(value).encode("utf-8"))

    # File part
    filename = os.path.basename(file_path)
    lines.append(f"--{boundary}".encode())
    lines.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'
        .encode()
    )
    lines.append(f"Content-Type: {file_content_type}".encode())
    lines.append(b"")
    with open(file_path, "rb") as f:
        lines.append(f.read())

    lines.append(f"--{boundary}--".encode())
    lines.append(b"")

    body = b"\r\n".join(lines)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def _ssl_context(verify_ssl):
    """Return an SSL context matching the verify_ssl flag."""
    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def cmd_upload(base_url, api_key, params, verify_ssl):
    """Upload a file attachment to a document (2-step process)."""
    file_path = params.get("file")
    doc_id = params.get("documentId")
    display_name = params.get("name")

    if not file_path or not doc_id:
        print("upload requires --file and --documentId", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if not display_name:
        display_name = os.path.basename(file_path)

    file_size = os.path.getsize(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    # Step 1: Create attachment record
    create_body = {
        "name": display_name,
        "documentId": doc_id,
        "size": file_size,
        "contentType": content_type,
    }
    resp = api_request(base_url, api_key, "attachments.create", create_body, verify_ssl)

    data = resp.get("data", {})
    upload_url = data.get("uploadUrl")
    form_fields = data.get("form", {})
    attachment = data.get("attachment", {})

    if not upload_url:
        print("attachments.create did not return an uploadUrl", file=sys.stderr)
        sys.exit(1)

    # Step 2: Upload file bytes via multipart POST
    # uploadUrl may be relative (e.g. "/api/files.create") or absolute
    if upload_url.startswith("http"):
        full_upload_url = upload_url
    else:
        # Strip /api suffix from base_url since uploadUrl already includes /api
        origin = base_url.rstrip("/")
        if origin.endswith("/api"):
            origin = origin[:-4]
        full_upload_url = origin + upload_url

    body, ct_header = _build_multipart(form_fields, "file", file_path, content_type)

    headers = {
        "Content-Type": ct_header,
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(full_upload_url, data=body, headers=headers, method="POST")
    ctx = _ssl_context(verify_ssl)

    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            pass  # 200 is enough; response body may be empty
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"File upload HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"File upload failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    att_id = attachment.get("id", "")
    att_name = attachment.get("name", display_name)
    redirect_url = f"/api/attachments.redirect?id={att_id}"
    markdown = f"[{att_name} ({file_size})]({redirect_url})"

    return {
        "id": att_id,
        "name": att_name,
        "size": file_size,
        "contentType": content_type,
        "markdown": markdown,
    }


def cmd_download(base_url, api_key, params, verify_ssl):
    """Download an attachment by ID to a local file."""
    att_id = params.get("id")
    output_path = params.get("output")

    if not att_id or not output_path:
        print("download requires --id and --output", file=sys.stderr)
        sys.exit(1)

    # Get the redirect URL
    origin = base_url.rstrip("/")
    if origin.endswith("/api"):
        origin = origin[:-4]
    redirect_url = f"{origin}/api/attachments.redirect?id={att_id}"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(redirect_url, headers=headers, method="GET")
    ctx = _ssl_context(verify_ssl)

    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"Download HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Download failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(output_path, "wb") as f:
            f.write(data)
    except IOError as e:
        print(f"Error writing to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)

    return {
        "id": att_id,
        "output": output_path,
        "size": len(data),
    }


COMMAND_DISPATCH = {
    "replace": cmd_replace,
    "append": cmd_append,
    "prepend": cmd_prepend,
    "section-read": cmd_section_read,
    "section-delete": cmd_section_delete,
    "upload": cmd_upload,
    "download": cmd_download,
}


# ---------------------------------------------------------------------------
# Compact-mode filters
# ---------------------------------------------------------------------------

def _pick(obj, keys):
    """Return a new dict containing only the specified keys from obj."""
    return {k: obj[k] for k in keys if k in obj}


def _filter_tree(nodes):
    """Recursively keep only {id, title, url, children} from NavigationNode."""
    out = []
    for node in nodes:
        item = _pick(node, ("id", "title", "url"))
        children = node.get("children")
        if children:
            item["children"] = _filter_tree(children)
        else:
            item["children"] = []
        out.append(item)
    return out


FILTERS = {
    # documents
    "documents.info": lambda r: _pick(r["data"], ("id", "title", "text")),
    "documents.list": lambda r: _pick_list(r, ("id", "title", "updatedAt")),
    "documents.search": lambda r: _pick_list_search(r),
    "documents.search_titles": lambda r: _pick_list(r, ("id", "title")),
    "documents.create": lambda r: _pick(r["data"], ("id", "title", "url")),
    "documents.update": lambda r: _pick(r["data"], ("id", "title", "revision")),
    "documents.delete": lambda r: _pick(r, ("success",)),
    "documents.move": lambda r: [_pick(d, ("id", "title", "collectionId")) for d in r["data"]["documents"]],
    "documents.archive": lambda r: _pick(r["data"], ("id", "title")),
    "documents.restore": lambda r: _pick(r["data"], ("id", "title")),
    "documents.duplicate": lambda r: [_pick(d, ("id", "title", "url")) for d in r["data"]["documents"]],
    "documents.documents": lambda r: _filter_tree(r["data"]),
    # collections
    "collections.info": lambda r: _pick(r["data"], ("id", "name", "description")),
    "collections.list": lambda r: _pick_list(r, ("id", "name")),
    "collections.create": lambda r: _pick(r["data"], ("id", "name", "url")),
    "collections.update": lambda r: _pick(r["data"], ("id", "name")),
    "collections.delete": lambda r: _pick(r, ("success",)),
    "collections.documents": lambda r: _filter_tree(r["data"]),
    # comments
    "comments.create": lambda r: _pick(r["data"], ("id", "documentId", "createdAt")),
    "comments.list": lambda r: _pick_list_comments(r),
    # attachments
    "attachments.delete": lambda r: _pick(r, ("success",)),
}


def _pick_list(response, keys):
    """Filter a list endpoint, preserving pagination."""
    items = [_pick(item, keys) for item in response.get("data", [])]
    result = items
    pagination = response.get("pagination")
    if pagination:
        result = {"data": items, "pagination": pagination}
    return result


def _pick_list_search(response):
    """Filter documents.search results."""
    items = []
    for entry in response.get("data", []):
        item = _pick(entry, ("ranking", "context"))
        doc = entry.get("document")
        if doc:
            item["document"] = _pick(doc, ("id", "title"))
        items.append(item)
    pagination = response.get("pagination")
    if pagination:
        return {"data": items, "pagination": pagination}
    return items


def _pick_list_comments(response):
    """Filter comments.list results."""
    items = []
    for entry in response.get("data", []):
        item = _pick(entry, ("id", "text", "createdAt"))
        created_by = entry.get("createdBy")
        if created_by:
            item["createdBy"] = _pick(created_by, ("name",))
        items.append(item)
    pagination = response.get("pagination")
    if pagination:
        return {"data": items, "pagination": pagination}
    return items


# ---------------------------------------------------------------------------
# Type coercion
# ---------------------------------------------------------------------------

def coerce_value(value):
    """Coerce string CLI values to appropriate Python types."""
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


# ---------------------------------------------------------------------------
# API request
# ---------------------------------------------------------------------------

def api_request(base_url, api_key, endpoint, body, verify_ssl=True):
    """Send a POST request to the Outline API and return parsed JSON."""
    url = f"{base_url.rstrip('/')}/{endpoint}"

    data = json.dumps(body).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    ssl_context = None
    if not verify_ssl:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ssl_context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Request failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_file_arg(path):
    """Read file content for --*-file= arguments."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        sys.exit(1)


# Map of --*-file= args to the param key they populate
_FILE_ARGS = {
    "--text-file=": "text",
    "--old-file=": "old",
    "--new-file=": "new",
}


def parse_args(argv):
    """Parse CLI arguments into (endpoint, params, raw)."""
    endpoint = None
    params = {}
    raw = False

    for arg in argv:
        if arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        elif arg == "--raw":
            raw = True
        elif any(arg.startswith(prefix) for prefix in _FILE_ARGS):
            for prefix, key in _FILE_ARGS.items():
                if arg.startswith(prefix):
                    params[key] = _read_file_arg(arg[len(prefix):])
                    break
        elif arg.startswith("--"):
            key, _, value = arg[2:].partition("=")
            if not value and not _:
                print(f"Invalid argument (missing value): {arg}", file=sys.stderr)
                sys.exit(1)
            params[key] = coerce_value(value)
        elif endpoint is None:
            endpoint = arg
        else:
            print(f"Unexpected positional argument: {arg}", file=sys.stderr)
            sys.exit(1)

    return endpoint, params, raw


def _get_env():
    """Read and validate environment variables."""
    api_key = os.environ.get("OUTLINE_API_KEY")
    base_url = os.environ.get("OUTLINE_API_URL")
    if not api_key:
        print("Error: OUTLINE_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    if not base_url:
        print("Error: OUTLINE_API_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    verify_ssl = os.environ.get("OUTLINE_SSL_VERIFY", "").lower() != "false"
    return base_url, api_key, verify_ssl


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    endpoint, params, raw = parse_args(sys.argv[1:])

    if endpoint is None:
        print(__doc__)
        sys.exit(1)

    base_url, api_key, verify_ssl = _get_env()

    # High-level commands: fetch → modify → update internally
    if endpoint in COMMAND_DISPATCH:
        output = COMMAND_DISPATCH[endpoint](base_url, api_key, params, verify_ssl)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    # Regular API endpoint
    response = api_request(base_url, api_key, endpoint, params, verify_ssl)

    if raw:
        output = response
    elif endpoint in FILTERS:
        try:
            output = FILTERS[endpoint](response)
        except (KeyError, TypeError):
            output = response.get("data", response)
    else:
        output = response.get("data", response)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
