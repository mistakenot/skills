# HTML Boilerplate

Every `plan.html` starts with exactly this structure. Replace `$ID`, `$NAME`, and `$DATE` placeholders.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$ID: $NAME</title>
  <script type="application/json" id="pd-meta">
  {
    "id": "$ID",
    "name": "$NAME",
    "status": "planning",
    "branch": null,
    "epic": null,
    "created": "$DATE",
    "pr": null
  }
  </script>
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <script src="https://cdn.jsdelivr.net/gh/mistakenot/skills@pd-v0.3.0/pd-components/dist/pd.min.js" defer></script>
</head>
<body>
  <pd-doc title="$ID: $NAME" status="draft" pr="pending" generated="$DATE">
    <!-- Tabs are added by each planning stage -->
  </pd-doc>
</body>
</html>
```

## Rules

- Use a CLASSIC script tag for pd-components (not `type="module"` — module scripts are CORS-blocked from `file://`).
- `pd-meta` goes in `<head>` as `<script type="application/json" id="pd-meta">`. Set `status` to `"planning"` and leave `branch`, `epic`, `pr` as `null`.
- `pd-doc` attributes: `status="draft"`, `pr="pending"`, `generated` = today's date.
- Tailwind is included for optional wireframe/layout content. pd-* components style themselves.
- Never modify or remove the `pd-meta` block once created — it tracks task lifecycle state managed by the workflow.
