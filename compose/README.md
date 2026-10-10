# compose/ — future sections

Drop per-domain fragments here (e.g. `observability.yaml`, `ml.yaml`) and
pull them in with a top-level `include:` block in `compose.yaml`, e.g.:

```yaml
include:
  - compose/observability.yaml
```

Keeps the base file minimal; each section stays independently reviewable.
