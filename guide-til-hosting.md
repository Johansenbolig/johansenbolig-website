# Guide: Sådan får du din nye hjemmeside online

Denne guide tager dig igennem alle trin – fra oprettelse af konti til domænet peger på den nye side. Sæt ca. 20-30 minutter af.

## Trin 1: Opret en GitHub-konto

GitHub er stedet, hvor sidens filer ligger (gratis).

1. Gå til [github.com/signup](https://github.com/signup)
2. Indtast din email, opret et password, og vælg et brugernavn
3. Bekræft din email, når GitHub sender dig en kode

## Trin 2: Opret et "repository" og upload filerne

1. Klik på **+** øverst til højre → **New repository**
2. Kald det f.eks. `johansenbolig-website` → sæt det til **Public** → klik **Create repository**
3. Klik på **"uploading an existing file"** (link midt på siden)
4. Træk alle filerne og mapperne fra den zip-fil, jeg har givet dig (pakket ud), ind i feltet
5. Klik **Commit changes** nederst

## Trin 3: Opret en Netlify-konto og forbind siden

Netlify er stedet, der viser siden på internettet (gratis for denne type side).

1. Gå til [app.netlify.com/signup](https://app.netlify.com/signup) og vælg **"Sign up with GitHub"**
2. Godkend adgangen til GitHub, når du bliver spurgt
3. Klik **Add new site → Import an existing project**
4. Vælg **GitHub** og find dit `johansenbolig-website` repository
5. Lad felterne **Build command** stå tomt, og sæt **Publish directory** til `.` (et enkelt punktum)
6. Klik **Deploy site**

Efter ca. et minut får du et link som `noget-tilfældigt-navn.netlify.app` – det er din side online.

## Trin 4: Slå redigering (CMS) til

1. I Netlify, gå til **Site configuration → Identity** → klik **Enable Identity**
2. Under **Registration preferences**, vælg **Invite only** (så det kun er dig, der kan logge ind)
3. Gå til **Identity → Services** og klik **Enable Git Gateway**
4. Gå tilbage til fanen **Identity** og klik **Invite users** → skriv din egen email
5. Tjek din indbakke og klik linket for at sætte et password

Nu kan du gå ind på `dit-site-navn.netlify.app/admin` og logge ind for at redigere tekst og billeder.

## Trin 5: Peg dit domæne (johansenbolig.dk) på den nye side

Domænet bliver ved med at ligge hos nordicway.dk – vi ændrer bare, hvor det "peger" hen.

1. I Netlify: **Site configuration → Domain management → Add a domain** → skriv `johansenbolig.dk`
2. Netlify viser dig nogle DNS-oplysninger (typisk en **A-record** og en **CNAME** for "www")
3. Log ind på din konto hos **nordicway.dk** og find **DNS-indstillinger** for domænet
4. Indsæt de værdier, Netlify viste dig, i stedet for de nuværende (dem der peger på Squarespace)
5. Gem ændringerne

Det kan tage fra få minutter til 24 timer, før ændringen slår igennem alle steder. Netlify sætter automatisk gratis SSL (det grønne hængelåsikon) op, når domænet er forbundet.

## Trin 6: Opsig Squarespace

Når johansenbolig.dk viser den nye side korrekt (tjek gerne fra din telefon på mobilnet, ikke kun hjemme-wifi, da DNS-ændringer nogle gange vises forskelligt), kan du opsige dit Squarespace-abonnement.

---

**Har du brug for hjælp undervejs** – f.eks. hvis en DNS-værdi ser forkert ud, eller noget fejler i Netlify – så send mig et skærmbillede, så hjælper jeg dig videre.
