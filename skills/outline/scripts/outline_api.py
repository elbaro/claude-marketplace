#!/usr/bin/env python3
"""CLI wrapper for the Outline wiki REST API.

Usage:
    python3 outline_api.py <endpoint> [--key=value ...] [--raw] [--text-file=path]

Examples:
    python3 outline_api.py documents.info --id=abc123
    python3 outline_api.py documents.list --collectionId=xyz --limit=5
    python3 outline_api.py documents.search --query="search term"
    python3 outline_api.py documents.create --title="New Doc" --collectionId=xyz --text-file=draft.md
    python3 outline_api.py collections.list --raw

Environment variables:
    OUTLINE_API_KEY      API token for authentication (required)
    OUTLINE_API_URL      Base URL of the Outline instance (required)
    OUTLINE_SSL_VERIFY   Set to "false" to disable SSL verification (optional)
"""

import json
import os
import ssl
import sys
import urllib.request
import urllib.error


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

def parse_args(argv):
    """Parse CLI arguments into (endpoint, params, raw, text_file)."""
    endpoint = None
    params = {}
    raw = False
    text_file = None

    for arg in argv:
        if arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        elif arg == "--raw":
            raw = True
        elif arg.startswith("--text-file="):
            text_file = arg.split("=", 1)[1]
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

    return endpoint, params, raw, text_file


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    endpoint, params, raw, text_file = parse_args(sys.argv[1:])

    if endpoint is None:
        print(__doc__)
        sys.exit(1)

    # Read text from file if specified
    if text_file is not None:
        try:
            with open(text_file, "r", encoding="utf-8") as f:
                params["text"] = f.read()
        except FileNotFoundError:
            print(f"File not found: {text_file}", file=sys.stderr)
            sys.exit(1)
        except IOError as e:
            print(f"Error reading file {text_file}: {e}", file=sys.stderr)
            sys.exit(1)

    # Environment variables
    api_key = os.environ.get("OUTLINE_API_KEY")
    base_url = os.environ.get("OUTLINE_API_URL")

    if not api_key:
        print("Error: OUTLINE_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    if not base_url:
        print("Error: OUTLINE_API_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    verify_ssl = os.environ.get("OUTLINE_SSL_VERIFY", "").lower() != "false"

    # Make the request
    response = api_request(base_url, api_key, endpoint, params, verify_ssl)

    # Apply filtering
    if raw:
        output = response
    elif endpoint in FILTERS:
        try:
            output = FILTERS[endpoint](response)
        except (KeyError, TypeError):
            # Fall back to raw data on filter failure
            output = response.get("data", response)
    else:
        output = response.get("data", response)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
