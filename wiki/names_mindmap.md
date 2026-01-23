# Project Name Ideas for IMAP-Based Mail Forwarder

> I want to build a lightweight mailing‑list‑style forwarder on top of an existing IMAP account.
> Here are some advantages for this instead of directly accessing the SMTP layer:
> Using a hosted mailbox gives you:
> - built‑in spam filtering
> - DKIM/DMARC/SPF handled by the provider
> - no need to run an MTA
> - no need to expose ports or manage TLS certificates
>
> Now I need to workshop some ideas for the project name. Can you propose some repository/project names?

Absolutely — this is a fun naming space because your tool sits right at the intersection of *mail routing*, *simplicity*, and *piggy‑backing on IMAP instead of running an MTA*. Here are several angles you can explore, each with concrete name ideas.

## ✉️ Names emphasizing IMAP‑based forwarding
- **imap‑relay**
- **imap‑forwarder**
- **imap‑list**
- **imap‑fanout**
- **imap‑router**
- **imap‑multipost**
- **imap‑hub**

## 🪶 Names emphasizing lightweight, minimal infrastructure
- **featherlist**
- **lightpost**
- **postling**
- **mail‑lite**
- **skimlist**
- **thinlist**
- **leanpost**

## 🔁 Names emphasizing “mailing‑list‑style” behavior
- **looplist**
- **fanmail**
- **listflow**
- **mailcascade**
- **poststream**
- **listrelay**
- **mailfan**

## 📬 Names inspired by mail metaphors
- **pigeonhub**
- **postbox‑relay**
- **mailhopper**
- **mailbridge**
- **postforward**
- **mailturnstile**
- **mailcarousel**

## 🧩 Names emphasizing “built on top of a hosted mailbox”
- **piggyback‑mail**
- **mail‑on‑rails**
- **mail‑piggy**
- **mail‑adapter**
- **mail‑shim**
- **mail‑proxy‑imap**

## 🧠 Slightly more playful / brandable names
- **Imapster**
- **Forwardo**
- **Listo**
- **Mailspin**
- **Mailmorph**
- **Posty**
- **Imaplane**

If you want, I can help you refine toward a specific vibe — professional, playful, minimalistic, sysadmin‑friendly, or something that fits your existing GitHub naming style.

# Final decision: Mailconveyor

`mailbridge` already [exists](https://pypi.org/project/mailbridge/).

`mailconveyor` is a great description of the wanted functionality without defining the problem space too small. It also doesn't exist yet.

