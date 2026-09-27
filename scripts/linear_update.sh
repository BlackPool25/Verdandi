#!/usr/bin/env bash
set -u
set -e
set -o pipefail

# scripts/linear_update.sh - Post CI status to Linear issue MINIPRO-18
# Fail-closed in CI when LINEAR_API_KEY is missing.

DRY_RUN=false
RAW_PAYLOAD=""

# Parse flags and arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      if [ -z "$RAW_PAYLOAD" ]; then
        RAW_PAYLOAD="$1"
      fi
      shift
      ;;
  esac
done

# Requirement: empty argument must fail (exit != 0)
if [ -z "${RAW_PAYLOAD// /}" ]; then
  echo "Error: Payload argument is required and cannot be empty" >&2
  exit 1
fi

KEY="${LINEAR_API_KEY:-}"
GA="${GITHUB_ACTIONS:-}"

# Dry-run handling: prints redacted payload and planned request without making network calls
if [ "$DRY_RUN" = "true" ]; then
  python3 - "$RAW_PAYLOAD" "$KEY" <<'EOF'
import sys, json

raw = sys.argv[1].strip()
secret_key = sys.argv[2] if len(sys.argv) > 2 else ""

def determine_status(raw_val):
    if raw_val.lower() in ("success", "green", "passed", "true"):
        return "SUCCESS"
    if raw_val.lower() in ("failure", "failed", "red", "cancelled", "false"):
        return "FAILED"
    try:
        data = json.loads(raw_val)
    except Exception:
        return "FAILED"

    if isinstance(data, dict):
        if not data:
            return "FAILED"
        for k, v in data.items():
            res = ""
            if isinstance(v, dict):
                res = str(v.get("result", "")).lower()
            elif isinstance(v, str):
                res = str(v).lower()
            if res in ("failure", "failed", "cancelled"):
                return "FAILED"
            if res not in ("success", "skipped"):
                return "FAILED"
        return "SUCCESS"
    elif isinstance(data, str):
        return "SUCCESS" if data.lower() in ("success", "green", "passed", "true") else "FAILED"
    return "FAILED"

status = determine_status(raw)

def redact(val):
    if isinstance(val, dict):
        new_d = {}
        for k, v in val.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("key", "token", "secret", "auth", "pass", "cred")):
                new_d[k] = "[REDACTED]"
            else:
                new_d[k] = redact(v)
        return new_d
    elif isinstance(val, list):
        return [redact(x) for x in val]
    elif isinstance(val, str):
        if secret_key and secret_key in val:
            val = val.replace(secret_key, "[REDACTED]")
        return val
    return val

parsed_json = None
try:
    parsed_json = json.loads(raw)
    redacted_obj = redact(parsed_json)
    redacted_str = json.dumps(redacted_obj)
except Exception:
    redacted_str = raw
    if secret_key and secret_key in redacted_str:
        redacted_str = redacted_str.replace(secret_key, "[REDACTED]")

if isinstance(redacted_obj, dict):
    body_lines = [f"### CI Pipeline Status: {status}\n"]
    for k, v in sorted(redacted_obj.items()):
        res = v.get("result", v) if isinstance(v, dict) else v
        icon = "✅" if str(res).lower() == "success" else "❌"
        body_lines.append(f"- {icon} **{k}**: `{res}`")
    comment_body = "\n".join(body_lines)
else:
    comment_body = f"### CI Pipeline Status: {status}\n\nStatus: `{status}`"

if secret_key and secret_key in comment_body:
    comment_body = comment_body.replace(secret_key, "[REDACTED]")

graphql_payload = {
    "query": "mutation CommentCreate($input: CommentCreateInput!) { commentCreate(input: $input) { success comment { id } } }",
    "variables": {
        "input": {
            "issueId": "MINIPRO-18",
            "body": comment_body
        }
    }
}

print(f"[DRY-RUN] Target issue: MINIPRO-18")
print(f"[DRY-RUN] Status: {status}")
print(f"[DRY-RUN] Redacted payload: {redacted_str}")
print("[DRY-RUN] Planned request:")
print("POST https://api.linear.app/graphql")
print("Headers:")
print("  Authorization: [REDACTED]")
print("  Content-Type: application/json")
print("Body:")
print(json.dumps(graphql_payload, indent=2))
EOF
  exit 0
fi

# Key & Environment Handling
if [ -z "$KEY" ]; then
  if [ "$GA" = "true" ]; then
    echo "::warning::LINEAR_API_KEY missing in CI environment"
    exit 1
  else
    echo "SKIP: LINEAR_API_KEY not set (local environment)"
    exit 0
  fi
fi

# Parse payload and prepare GraphQL mutation
PYTHON_OUTPUT=$(python3 - "$RAW_PAYLOAD" "$KEY" <<'EOF'
import sys, json

raw = sys.argv[1].strip()

def determine_status(raw_val):
    if raw_val.lower() in ("success", "green", "passed", "true"):
        return "SUCCESS"
    if raw_val.lower() in ("failure", "failed", "red", "cancelled", "false"):
        return "FAILED"
    try:
        data = json.loads(raw_val)
    except Exception:
        return "FAILED"

    if isinstance(data, dict):
        if not data:
            return "FAILED"
        for k, v in data.items():
            res = ""
            if isinstance(v, dict):
                res = str(v.get("result", "")).lower()
            elif isinstance(v, str):
                res = str(v).lower()
            if res in ("failure", "failed", "cancelled"):
                return "FAILED"
            if res not in ("success", "skipped"):
                return "FAILED"
        return "SUCCESS"
    elif isinstance(data, str):
        return "SUCCESS" if data.lower() in ("success", "green", "passed", "true") else "FAILED"
    return "FAILED"

status = determine_status(raw)

def redact(val):
    if isinstance(val, dict):
        new_d = {}
        for k, v in val.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("key", "token", "secret", "auth", "pass", "cred")):
                new_d[k] = "[REDACTED]"
            else:
                new_d[k] = redact(v)
        return new_d
    elif isinstance(val, list):
        return [redact(x) for x in val]
    elif isinstance(val, str):
        if secret_key and secret_key in val:
            val = val.replace(secret_key, "[REDACTED]")
        return val
    return val

redacted_obj = None
try:
    parsed_json = json.loads(raw)
    redacted_obj = redact(parsed_json)
except Exception:
    redacted_obj = None

if isinstance(redacted_obj, dict):
    body_lines = [f"### CI Pipeline Status: {status}\n"]
    for k, v in sorted(redacted_obj.items()):
        res = v.get("result", v) if isinstance(v, dict) else v
        icon = "✅" if str(res).lower() == "success" else "❌"
        body_lines.append(f"- {icon} **{k}**: `{res}`")
    comment_body = "\n".join(body_lines)
else:
    comment_body = f"### CI Pipeline Status: {status}\n\nStatus: `{status}`"

if secret_key and secret_key in comment_body:
    comment_body = comment_body.replace(secret_key, "[REDACTED]")

graphql_payload = {
    "query": "mutation CommentCreate($input: CommentCreateInput!) { commentCreate(input: $input) { success comment { id } } }",
    "variables": {
        "input": {
            "issueId": "MINIPRO-18",
            "body": comment_body
        }
    }
}

output = {
    "status": status,
    "graphql_payload": json.dumps(graphql_payload)
}
print(json.dumps(output))
EOF
)

STATUS=$(python3 -c "import sys, json; print(json.loads(sys.argv[1])['status'])" "$PYTHON_OUTPUT")
GRAPHQL_BODY=$(python3 -c "import sys, json; print(json.loads(sys.argv[1])['graphql_payload'])" "$PYTHON_OUTPUT")

# Post to Linear GraphQL API
# NEVER echo or leak LINEAR_API_KEY in logs or error output
set +e
CURL_OUTPUT=$(curl -sS -X POST "https://api.linear.app/graphql" \
  -H "Authorization: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "${GRAPHQL_BODY}" 2>&1)
CURL_STATUS=$?
set -e

# Sanitize output by redacting the API key
CLEAN_OUTPUT="${CURL_OUTPUT//"$KEY"/"[REDACTED]"}"

if [ $CURL_STATUS -ne 0 ]; then
  echo "Error: curl connection failed with exit code $CURL_STATUS" >&2
  echo "$CLEAN_OUTPUT" >&2
  exit 1
fi

if echo "$CLEAN_OUTPUT" | grep -q '"errors"'; then
  echo "Error: Linear GraphQL API returned an error:" >&2
  echo "$CLEAN_OUTPUT" >&2
  exit 1
fi

echo "Linear status successfully posted to MINIPRO-18: status ${STATUS}"
exit 0
