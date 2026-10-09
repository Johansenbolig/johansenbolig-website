# Johansen Bolig — ny hjemmeside

Repository: github.com/Johansenbolig/johansenbolig-website

Statisk side uden build-trin. Netlify udgiver mappen direkte.

## Indhold
- `index.html` — hele siden (Forside, Trippelhusene, Oluf Bagers Gade 40, Ledige)
- `support.js`, `image-slot.js` — runtime (rør ikke)
- `billeder/` — fotos
- `netlify.toml` — Netlify-opsætning (sender gamle /om-os.html og /kontakt.html videre til forsiden)

## Upload til GitHub (erstatter den gamle side)
1. Åbn github.com/Johansenbolig/johansenbolig-website
2. **Add file → Upload files** → træk *indholdet* af denne mappe ind (index.html, netlify.toml, support.js, image-slot.js, robots.txt, README.md og mappen billeder).
3. Svar ja til at overskrive `index.html` og `netlify.toml`.
4. **Commit changes**.

Gamle filer, der ikke længere bruges (kan slettes bagefter): `om-os.html`, `kontakt.html`, `assets/`, `content/`, `admin/`.
Bemærk: `/admin`-redigering (CMS) virker ikke med det nye design.

## Netlify
Hvis sitet allerede er forbundet til repo'et, udgiver Netlify automatisk efter ~1 minut.
Ellers: app.netlify.com → **Add new site → Import an existing project → GitHub** → vælg repo'et → Build command tom, Publish directory `.` → **Deploy**.

## Domæne (johansenbolig.dk hos nordicway.dk)
1. Netlify → *Domain management → Add a domain* → `johansenbolig.dk`.
2. Hos nordicway.dk: erstat de DNS-records, der peger på Squarespace, med Netlifys (A-record `@` og CNAME `www`).
3. Rør ikke MX-records (mail). HTTPS slås til automatisk.
