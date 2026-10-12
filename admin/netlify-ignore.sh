#!/bin/bash
# Netlify kører dette før hver udgivelse (Build settings → Ignore builds:
#   bash admin/netlify-ignore.sh). Exit 0 = spring over, exit 1 = udgiv.
# Rettelser fra redigeringspanelet ændrer kun admin/indstillinger.json, og den
# fil læses direkte fra GitHub af siden. Så kræver de ingen ny udgivelse – det sparer credits.
if [ -z "$CACHED_COMMIT_REF" ] || [ "$CACHED_COMMIT_REF" = "$COMMIT_REF" ]; then
  exit 1
fi
if git diff --quiet "$CACHED_COMMIT_REF" "$COMMIT_REF" -- . ':(exclude)admin/indstillinger.json'; then
  echo "Kun admin/indstillinger.json er ændret – springer udgivelse over."
  exit 0
fi
exit 1
