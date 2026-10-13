# Mailværktøj – Johansen Bolig

`mailkasse.py` læser og skriver i mailboksene hos Nordicway via IMAP/SMTP.
Kun Pythons standardbibliotek (Python 3.9+), intet at installere.

| Konto     | Adresse                   | Kodeord i miljøvariabel |
|-----------|---------------------------|-------------------------|
| `niels`   | niels@johansenbolig.dk    | `MAIL_NIELS_KODE`       |
| `kontakt` | kontakt@johansenbolig.dk  | `MAIL_KONTAKT_KODE`     |

Server: `mail.johansenbolig.dk` – IMAP 993 (SSL), SMTP 465 (SSL).
Kan overstyres med `MAIL_VAERT`, `MAIL_IMAP_PORT`, `MAIL_SMTP_PORT`.

Kodeord ligger **aldrig** i repo'et – kun i miljøvariabler.

## Kommandoer

```
python3 mailvaerktoej/mailkasse.py test                      # login-test af begge konti (sender intet)
python3 mailvaerktoej/mailkasse.py mapper kontakt
python3 mailvaerktoej/mailkasse.py liste kontakt --ulaeste --antal 20
python3 mailvaerktoej/mailkasse.py liste niels --siden 2026-10-01 --soeg lejlighed
python3 mailvaerktoej/mailkasse.py laes kontakt 1234          # markerer IKKE som læst
python3 mailvaerktoej/mailkasse.py kladde kontakt --svar-paa 1234 --tekst "..."   # gemmes i Kladder
python3 mailvaerktoej/mailkasse.py svar kontakt 1234 --tekst "..."
python3 mailvaerktoej/mailkasse.py send niels --til a@b.dk --emne "Hej" --tekst "..." --vedhaeft fil.pdf
python3 mailvaerktoej/mailkasse.py marker kontakt 1234 --laest
python3 mailvaerktoej/mailkasse.py flyt kontakt 1234 papirkurv
```

`--json` før kommandoen giver maskinlæsbart output, fx `mailkasse.py --json liste kontakt`.
`kladde` er det sikre valg ved automatiske opgaver: svaret ligger klar i Kladder, og
du sender det selv efter gennemlæsning.

Mappen udgives ikke på hjemmesiden (se `netlify.toml`), og ændringer her starter
ikke en ny Netlify-udgivelse (se `admin/netlify-ignore.sh`).
