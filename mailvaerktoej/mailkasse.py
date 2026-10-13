#!/usr/bin/env python3
"""Læs og skriv i Johansen Boligs mailbokse (hos Nordicway) via IMAP/SMTP.

Kun Pythons standardbibliotek – intet skal installeres.

Konti (kodeord læses fra miljøvariabler, aldrig fra filer):
  niels    niels@johansenbolig.dk    MAIL_NIELS_KODE
  kontakt  kontakt@johansenbolig.dk  MAIL_KONTAKT_KODE

Eksempler:
  python3 mailkasse.py test
  python3 mailkasse.py mapper kontakt
  python3 mailkasse.py liste kontakt --ulaeste --antal 10
  python3 mailkasse.py laes kontakt 1234
  python3 mailkasse.py kladde kontakt --svar-paa 1234 --tekst "Tak for din mail ..."
  python3 mailkasse.py send niels --til a@b.dk --emne "Hej" --tekst "..."
  python3 mailkasse.py svar kontakt 1234 --tekst "..."
  python3 mailkasse.py marker kontakt 1234 --laest
  python3 mailkasse.py flyt kontakt 1234 Arkiv

Tilføj --json før kommandoen for maskinlæsbart output.
"""

import argparse
import base64
import email
import email.policy
import html
import imaplib
import json
import mimetypes
import os
import re
import smtplib
import socket
import ssl
import sys
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate, getaddresses, make_msgid, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

VAERT = os.environ.get("MAIL_VAERT", "mail.johansenbolig.dk")
IMAP_PORT = int(os.environ.get("MAIL_IMAP_PORT", "993"))
SMTP_PORT = int(os.environ.get("MAIL_SMTP_PORT", "465"))
TIMEOUT = 60

KONTI = {
    "niels": {"adresse": "niels@johansenbolig.dk", "navn": "Niels Johansen", "kode_var": "MAIL_NIELS_KODE"},
    "kontakt": {"adresse": "kontakt@johansenbolig.dk", "navn": "Johansen Bolig", "kode_var": "MAIL_KONTAKT_KODE"},
}


class Fejl(Exception):
    pass


# --------------------------------------------------------------------------
# Forbindelse (direkte, eller gennem en HTTP-proxy med CONNECT i skyen)
# --------------------------------------------------------------------------

def _proxy_til(vaert):
    url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not url:
        return None
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    for m in (x.strip().lstrip("*") for x in no_proxy.split(",") if x.strip()):
        if vaert == m.lstrip(".") or (m.startswith(".") and vaert.endswith(m)):
            return None
    p = urlparse(url)
    return p.hostname, p.port or 80


def _aaben_sokkel(vaert, port, timeout):
    proxy = _proxy_til(vaert)
    if not proxy:
        return socket.create_connection((vaert, port), timeout)
    s = socket.create_connection(proxy, timeout)
    s.sendall(f"CONNECT {vaert}:{port} HTTP/1.1\r\nHost: {vaert}:{port}\r\n\r\n".encode())
    svar = b""
    while b"\r\n\r\n" not in svar:
        bid = s.recv(4096)
        if not bid:
            break
        svar += bid
    statuslinje = svar.split(b"\r\n", 1)[0].decode(errors="replace")
    if " 200 " not in statuslinje + " ":
        s.close()
        raise Fejl(f"Proxyen afviste forbindelsen til {vaert}:{port} ({statuslinje}). "
                   "Værten skal tillades i miljøets netværksindstillinger.")
    return s


def _tls():
    return ssl.create_default_context()


class _IMAP(imaplib.IMAP4_SSL):
    def _create_socket(self, timeout):
        s = _aaben_sokkel(self.host, self.port, timeout or TIMEOUT)
        return self.ssl_context.wrap_socket(s, server_hostname=self.host)


class _SMTP(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        s = _aaben_sokkel(host, port, timeout or TIMEOUT)
        return self.context.wrap_socket(s, server_hostname=host)


def _konto(navn):
    if navn not in KONTI:
        raise Fejl(f"Ukendt konto '{navn}'. Brug: {', '.join(KONTI)}")
    k = dict(KONTI[navn])
    k["kode"] = os.environ.get(k["kode_var"])
    if not k["kode"]:
        raise Fejl(f"Miljøvariablen {k['kode_var']} er ikke sat (kodeord til {k['adresse']}).")
    return k


def imap_login(navn):
    k = _konto(navn)
    m = _IMAP(VAERT, IMAP_PORT, ssl_context=_tls(), timeout=TIMEOUT)
    try:
        m.login(k["adresse"], k["kode"])
    except imaplib.IMAP4.error as e:
        raise Fejl(f"IMAP-login fejlede for {k['adresse']}: {e}")
    return m, k


def smtp_login(navn):
    k = _konto(navn)
    s = _SMTP(VAERT, SMTP_PORT, context=_tls(), timeout=TIMEOUT)
    try:
        s.login(k["adresse"], k["kode"])
    except smtplib.SMTPException as e:
        raise Fejl(f"SMTP-login fejlede for {k['adresse']}: {e}")
    return s, k


# --------------------------------------------------------------------------
# Mappenavne (IMAP bruger "modificeret UTF-7", fx "Sendt post" / "Kladder")
# --------------------------------------------------------------------------

def mutf7_afkod(s):
    def erstat(m):
        indhold = m.group(1)
        if indhold == "":
            return "&"
        b = indhold.replace(",", "/")
        b += "=" * (-len(b) % 4)
        return base64.b64decode(b).decode("utf-16-be")
    return re.sub(r"&([^-]*)-", erstat, s)


def mutf7_kod(s):
    ud, buf = [], []

    def toem():
        if buf:
            b = base64.b64encode("".join(buf).encode("utf-16-be")).decode().rstrip("=")
            ud.append("&" + b.replace("/", ",") + "-")
            buf.clear()
    for c in s:
        if 0x20 <= ord(c) <= 0x7E:
            toem()
            ud.append("&-" if c == "&" else c)
        else:
            buf.append(c)
    toem()
    return "".join(ud)


def _q(mappe):
    kodet = mutf7_kod(mappe).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{kodet}"'


_LIST_RE = re.compile(r'\((?P<flag>[^)]*)\) (?P<skil>"[^"]*"|NIL) (?P<navn>.+)')


def list_mapper(m):
    typ, data = m.list()
    if typ != "OK":
        raise Fejl("Kunne ikke liste mapper")
    mapper = []
    for linje in data:
        if not linje:
            continue
        if isinstance(linje, tuple):
            linje = linje[0] + b" " + linje[1]
        mt = _LIST_RE.match(linje.decode(errors="replace"))
        if not mt:
            continue
        navn = mt.group("navn").strip()
        if navn.startswith('"') and navn.endswith('"'):
            navn = navn[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        mapper.append({"navn": mutf7_afkod(navn), "flag": mt.group("flag").split()})
    return mapper


_SAERLIGE = {
    "sendt": ("\\Sent", ["Sent", "INBOX.Sent", "Sendt", "Sendt post", "INBOX.Sendt", "Sent Items", "Sent Messages"]),
    "kladder": ("\\Drafts", ["Drafts", "INBOX.Drafts", "Kladder", "INBOX.Kladder"]),
    "papirkurv": ("\\Trash", ["Trash", "INBOX.Trash", "Papirkurv", "Deleted Items", "Slettet post"]),
    "spam": ("\\Junk", ["Junk", "INBOX.Junk", "Spam", "INBOX.spam", "Uønsket post"]),
}


def find_mappe(m, slags):
    flag, navne = _SAERLIGE[slags]
    mapper = list_mapper(m)
    for x in mapper:
        if flag in x["flag"]:
            return x["navn"]
    eksisterende = {x["navn"].lower(): x["navn"] for x in mapper}
    for n in navne:
        if n.lower() in eksisterende:
            return eksisterende[n.lower()]
    return None


def vaelg(m, mappe, skrivebeskyttet=True):
    typ, data = m.select(_q(mappe), readonly=skrivebeskyttet)
    if typ != "OK":
        raise Fejl(f"Mappen '{mappe}' findes ikke ({data[0].decode(errors='replace') if data else ''})")


# --------------------------------------------------------------------------
# Læsning
# --------------------------------------------------------------------------

def _hoved(msg, felt):
    v = msg.get(felt)
    return str(v) if v is not None else ""


def _dato(msg):
    try:
        return parsedate_to_datetime(msg["Date"]).isoformat()
    except Exception:
        return _hoved(msg, "Date")


def _html_til_tekst(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", "", h)
    h = html.unescape(h)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", h)).strip()


def broedtekst(msg):
    del_ = msg.get_body(preferencelist=("plain", "html"))
    if del_ is None:
        return ""
    try:
        indhold = del_.get_content()
    except Exception:
        indhold = (del_.get_payload(decode=True) or b"").decode("utf-8", "replace")
    return _html_til_tekst(indhold) if del_.get_content_type() == "text/html" else indhold.strip()


def vedhaeftninger(msg):
    ud = []
    for d in msg.iter_attachments():
        data = d.get_payload(decode=True) or b""
        ud.append({"filnavn": d.get_filename() or "(uden navn)", "type": d.get_content_type(), "bytes": len(data)})
    return ud


def hent(m, uid):
    typ, data = m.uid("FETCH", str(uid), "(FLAGS BODY.PEEK[])")
    if typ != "OK" or not data or data[0] is None or not isinstance(data[0], tuple):
        raise Fejl(f"Fandt ingen mail med UID {uid}")
    flag = imaplib.ParseFlags(data[0][0])
    msg = email.message_from_bytes(data[0][1], policy=email.policy.default)
    return msg, [f.decode() for f in flag], data[0][1]


_MAANEDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _soegekriterier(a):
    k = []
    if a.ulaeste:
        k.append("UNSEEN")
    if a.siden:
        t = time.strptime(a.siden, "%Y-%m-%d")
        k.append(f"SINCE {t.tm_mday}-{_MAANEDER[t.tm_mon - 1]}-{t.tm_year}")
    for noegle, v in (("FROM", a.fra), ("SUBJECT", a.emne), ("TEXT", a.soeg)):
        if v and v.isascii():
            k.append(f'{noegle} "' + v.replace("\\", "").replace('"', "") + '"')
    return k or ["ALL"]


def _soeg(m, kriterier):
    typ, data = m.uid("SEARCH", None, *kriterier)
    if typ != "OK":
        raise Fejl("Søgning fejlede")
    return [int(x) for x in data[0].split()]


def cmd_liste(a):
    m, k = imap_login(a.konto)
    try:
        vaelg(m, a.mappe)
        # Søgeord med æøå filtreres lokalt (fra/emne), da IMAP-søgning med UTF-8 er upålidelig
        lokal = not all(v.isascii() for v in (a.soeg, a.emne, a.fra) if v)
        uids = _soeg(m, _soegekriterier(a))
        uids = sorted(uids, reverse=True)
        resultat = []
        for i in range(0, len(uids), 50):
            if len(resultat) >= a.antal:
                break
            bid = uids[i:i + 50]
            typ, data = m.uid("FETCH", ",".join(map(str, bid)),
                              "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO DATE SUBJECT MESSAGE-ID)])")
            for d in data:
                if not isinstance(d, tuple):
                    continue
                uid = int(re.search(rb"UID (\d+)", d[0]).group(1))
                flag = [f.decode() for f in imaplib.ParseFlags(d[0])]
                h = email.message_from_bytes(d[1], policy=email.policy.default)
                r = {"uid": uid, "dato": _dato(h), "fra": _hoved(h, "From"), "til": _hoved(h, "To"),
                     "emne": _hoved(h, "Subject"), "laest": "\\Seen" in flag, "flag": flag}
                if lokal:
                    tjek = [(a.soeg, r["fra"] + r["emne"]), (a.emne, r["emne"]), (a.fra, r["fra"])]
                    if any(v and not v.isascii() and v.lower() not in felt.lower() for v, felt in tjek):
                        continue
                resultat.append(r)
        resultat.sort(key=lambda r: r["uid"], reverse=True)
        resultat = resultat[:a.antal]
        if a.json:
            udskriv_json({"konto": k["adresse"], "mappe": a.mappe, "antal_i_alt": len(uids), "mails": resultat})
        else:
            print(f"{k['adresse']} / {a.mappe}: {len(uids)} mails matcher, viser {len(resultat)}")
            for r in resultat:
                print(f"{'  ' if r['laest'] else '* '}{r['uid']:>7}  {r['dato'][:16]:16}  {r['fra'][:35]:35}  {r['emne']}")
    finally:
        m.logout()


def cmd_laes(a):
    m, k = imap_login(a.konto)
    try:
        vaelg(m, a.mappe, skrivebeskyttet=not a.marker_laest)
        msg, flag, raa = hent(m, a.uid)
        if a.marker_laest:
            m.uid("STORE", str(a.uid), "+FLAGS", "(\\Seen)")
        if a.gem_vedhaeftninger:
            mappe = Path(a.gem_vedhaeftninger)
            mappe.mkdir(parents=True, exist_ok=True)
            for d in msg.iter_attachments():
                navn = Path(d.get_filename() or "vedhaeftning.bin").name
                (mappe / navn).write_bytes(d.get_payload(decode=True) or b"")
        r = {"uid": a.uid, "mappe": a.mappe, "dato": _dato(msg), "fra": _hoved(msg, "From"), "til": _hoved(msg, "To"),
             "cc": _hoved(msg, "Cc"), "svar_til": _hoved(msg, "Reply-To"), "emne": _hoved(msg, "Subject"),
             "message_id": _hoved(msg, "Message-ID"), "flag": flag, "tekst": broedtekst(msg),
             "vedhaeftninger": vedhaeftninger(msg)}
        if a.json:
            udskriv_json(r)
        else:
            for felt in ("dato", "fra", "til", "cc", "svar_til", "emne"):
                if r[felt]:
                    print(f"{felt.capitalize():9} {r[felt]}")
            if r["vedhaeftninger"]:
                print("Vedhæftet " + ", ".join(f"{v['filnavn']} ({v['bytes'] // 1024} KB)" for v in r["vedhaeftninger"]))
            print("-" * 70)
            print(r["tekst"])
    finally:
        m.logout()


def cmd_mapper(a):
    m, k = imap_login(a.konto)
    try:
        mapper = list_mapper(m)
        if a.json:
            udskriv_json(mapper)
        else:
            for x in mapper:
                print(f"{x['navn']:30} {' '.join(x['flag'])}")
    finally:
        m.logout()


# --------------------------------------------------------------------------
# Skrivning
# --------------------------------------------------------------------------

def _byg(k, til, emne, tekst, cc=None, bcc=None, filer=(), svar_paa=None):
    msg = EmailMessage()
    msg["From"] = formataddr((k["navn"], k["adresse"]))
    msg["To"] = ", ".join(til)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = emne
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="johansenbolig.dk")
    if svar_paa is not None:
        mid = _hoved(svar_paa, "Message-ID")
        if mid:
            msg["In-Reply-To"] = mid
            msg["References"] = (_hoved(svar_paa, "References") + " " + mid).strip()
        citat = "\n".join("> " + l for l in broedtekst(svar_paa).splitlines())
        tekst = f"{tekst}\n\nDen {_hoved(svar_paa, 'Date')} skrev {_hoved(svar_paa, 'From')}:\n{citat}\n"
    msg.set_content(tekst)
    for f in filer:
        p = Path(f)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        hoved, under = ctype.split("/", 1)
        msg.add_attachment(p.read_bytes(), maintype=hoved, subtype=under, filename=p.name)
    return msg


def _svar_modtagere(k, orig, alle):
    til = [orig.get("Reply-To") or orig.get("From")]
    cc = []
    if alle:
        egne = {x["adresse"] for x in KONTI.values()}
        for _, adr in getaddresses([_hoved(orig, "To"), _hoved(orig, "Cc")]):
            if adr and adr.lower() not in egne and adr not in str(til[0]):
                cc.append(adr)
    emne = _hoved(orig, "Subject")
    if not re.match(r"(?i)^(re|sv|aw):", emne):
        emne = "Re: " + emne
    return [str(t) for t in til], cc, emne


def _laes_tekst(a):
    if a.fil:
        return Path(a.fil).read_text(encoding="utf-8")
    if a.tekst == "-":
        return sys.stdin.read()
    if a.tekst is None:
        raise Fejl("Angiv --tekst eller --fil")
    return a.tekst


def _gem_i(m, mappe, msg, flag):
    raa = msg.as_bytes(policy=email.policy.SMTP)
    typ, data = m.append(_q(mappe), flag, imaplib.Time2Internaldate(time.time()), raa)
    if typ != "OK":
        raise Fejl(f"Kunne ikke gemme i '{mappe}': {data}")


def _forbered(a, m, k):
    orig = None
    if getattr(a, "svar_paa", None) or getattr(a, "uid", None):
        vaelg(m, a.mappe)
        orig, _, _ = hent(m, a.svar_paa or a.uid)
        til, cc, emne = _svar_modtagere(k, orig, getattr(a, "alle", False))
        til = a.til or til
        cc = (a.cc or []) + cc
        emne = a.emne or emne
    else:
        if not a.til or not a.emne:
            raise Fejl("Angiv --til og --emne")
        til, cc, emne = a.til, a.cc or [], a.emne
    return _byg(k, til, emne, _laes_tekst(a), cc=cc, bcc=a.bcc, filer=a.vedhaeft or (), svar_paa=orig), orig


def cmd_kladde(a):
    m, k = imap_login(a.konto)
    try:
        msg, _ = _forbered(a, m, k)
        mappe = find_mappe(m, "kladder") or "Drafts"
        _gem_i(m, mappe, msg, "(\\Draft \\Seen)")
        _bekraeft(a, {"status": "kladde gemt", "konto": k["adresse"], "mappe": mappe,
                      "til": msg["To"], "emne": msg["Subject"]})
    finally:
        m.logout()


def _send(a):
    m, k = imap_login(a.konto)
    try:
        msg, orig = _forbered(a, m, k)
        s, _ = smtp_login(a.konto)
        try:
            s.send_message(msg)
        finally:
            s.quit()
        sendt = find_mappe(m, "sendt")
        if sendt and not a.ingen_kopi:
            del msg["Bcc"]
            _gem_i(m, sendt, msg, "(\\Seen)")
        if orig is not None:
            vaelg(m, a.mappe, skrivebeskyttet=False)
            m.uid("STORE", str(a.svar_paa or a.uid), "+FLAGS", "(\\Answered \\Seen)")
        _bekraeft(a, {"status": "sendt", "konto": k["adresse"], "til": msg["To"], "cc": msg["Cc"],
                      "emne": msg["Subject"], "kopi_i": sendt})
    finally:
        m.logout()


cmd_send = cmd_svar = _send


def cmd_marker(a):
    m, k = imap_login(a.konto)
    try:
        vaelg(m, a.mappe, skrivebeskyttet=False)
        aendringer = []
        if a.laest:
            aendringer.append(("+FLAGS", "(\\Seen)"))
        if a.ulaest:
            aendringer.append(("-FLAGS", "(\\Seen)"))
        if a.stjerne:
            aendringer.append(("+FLAGS", "(\\Flagged)"))
        if a.fjern_stjerne:
            aendringer.append(("-FLAGS", "(\\Flagged)"))
        if not aendringer:
            raise Fejl("Angiv --laest, --ulaest, --stjerne eller --fjern-stjerne")
        for op, flag in aendringer:
            m.uid("STORE", ",".join(map(str, a.uid)), op, flag)
        _bekraeft(a, {"status": "markeret", "uid": a.uid})
    finally:
        m.logout()


def cmd_flyt(a):
    m, k = imap_login(a.konto)
    try:
        maal = a.til_mappe
        if maal.lower() in _SAERLIGE:
            maal = find_mappe(m, maal.lower()) or maal
        vaelg(m, a.mappe, skrivebeskyttet=False)
        uids = ",".join(map(str, a.uid))
        typ, data = m.uid("MOVE", uids, _q(maal))
        if typ != "OK":
            typ, data = m.uid("COPY", uids, _q(maal))
            if typ != "OK":
                raise Fejl(f"Kunne ikke flytte til '{maal}': {data}")
            m.uid("STORE", uids, "+FLAGS", "(\\Deleted)")
            m.expunge()
        _bekraeft(a, {"status": "flyttet", "uid": a.uid, "til": maal})
    finally:
        m.logout()


def cmd_test(a):
    ok = True
    for navn in ([a.konto] if a.konto else KONTI):
        for proto, fn in (("IMAP", imap_login), ("SMTP", smtp_login)):
            try:
                forb, k = fn(navn)
                if proto == "IMAP":
                    typ, data = forb.status("INBOX", "(MESSAGES UNSEEN)")
                    info = data[0].decode(errors="replace")
                    forb.logout()
                else:
                    info = "login ok"
                    forb.quit()
                print(f"OK    {proto} {KONTI[navn]['adresse']}  {info}")
            except Exception as e:
                ok = False
                print(f"FEJL  {proto} {KONTI[navn]['adresse']}  {e}")
    if not ok:
        sys.exit(1)


# --------------------------------------------------------------------------

def udskriv_json(x):
    print(json.dumps(x, ensure_ascii=False, indent=2, default=str))


def _bekraeft(a, r):
    if a.json:
        udskriv_json(r)
    else:
        print(", ".join(f"{k}: {v}" for k, v in r.items() if v))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="maskinlæsbart output")
    sub = p.add_subparsers(dest="kommando", required=True)

    def ny(navn, hj, konto=True):
        sp = sub.add_parser(navn, help=hj)
        if konto:
            sp.add_argument("konto", choices=list(KONTI))
        sp.set_defaults(func=globals()["cmd_" + navn])
        return sp

    t = ny("test", "test login (IMAP og SMTP) – sender intet", konto=False)
    t.add_argument("konto", nargs="?", choices=list(KONTI))
    ny("mapper", "vis mapper")

    sp = ny("liste", "vis mails (markerer ikke som læst)")
    sp.add_argument("--mappe", default="INBOX")
    sp.add_argument("--antal", type=int, default=20)
    sp.add_argument("--ulaeste", action="store_true")
    sp.add_argument("--siden", metavar="ÅÅÅÅ-MM-DD")
    sp.add_argument("--fra")
    sp.add_argument("--emne")
    sp.add_argument("--soeg", help="fritekst")

    sp = ny("laes", "læs én mail (markerer ikke som læst, medmindre --marker-laest)")
    sp.add_argument("uid", type=int)
    sp.add_argument("--mappe", default="INBOX")
    sp.add_argument("--marker-laest", action="store_true")
    sp.add_argument("--gem-vedhaeftninger", metavar="MAPPE")

    def skriv(sp, svar):
        sp.add_argument("--mappe", default="INBOX", help="mappen med mailen der svares på")
        sp.add_argument("--til", nargs="+", required=False)
        sp.add_argument("--cc", nargs="+")
        sp.add_argument("--bcc", nargs="+")
        sp.add_argument("--emne")
        sp.add_argument("--tekst", help="brødtekst ('-' = læs fra stdin)")
        sp.add_argument("--fil", help="læs brødtekst fra fil")
        sp.add_argument("--vedhaeft", nargs="+", metavar="FIL")
        sp.add_argument("--alle", action="store_true", help="svar alle")
        if svar:
            sp.add_argument("uid", type=int)
            sp.set_defaults(svar_paa=None)
        else:
            sp.add_argument("--svar-paa", type=int, metavar="UID")
            sp.set_defaults(uid=None)

    sp = ny("kladde", "gem en kladde i Kladder-mappen (sender intet)")
    skriv(sp, svar=False)
    sp = ny("send", "send en ny mail")
    skriv(sp, svar=False)
    sp.add_argument("--ingen-kopi", action="store_true", help="gem ikke kopi i Sendt")
    sp = ny("svar", "svar på en mail")
    skriv(sp, svar=True)
    sp.add_argument("--ingen-kopi", action="store_true")

    sp = ny("marker", "markér som læst/ulæst/stjerne")
    sp.add_argument("uid", type=int, nargs="+")
    sp.add_argument("--mappe", default="INBOX")
    sp.add_argument("--laest", action="store_true")
    sp.add_argument("--ulaest", action="store_true")
    sp.add_argument("--stjerne", action="store_true")
    sp.add_argument("--fjern-stjerne", action="store_true")

    sp = ny("flyt", "flyt mails til en anden mappe (fx sendt, papirkurv, spam eller et navn)")
    sp.add_argument("uid", type=int, nargs="+")
    sp.add_argument("til_mappe")
    sp.add_argument("--mappe", default="INBOX")

    a = p.parse_args(argv)
    try:
        a.func(a)
    except Fejl as e:
        print(f"Fejl: {e}", file=sys.stderr)
        sys.exit(2)
    except (OSError, imaplib.IMAP4.error, smtplib.SMTPException) as e:
        print(f"Forbindelsesfejl ({type(e).__name__}): {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
