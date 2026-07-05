<div align="center">

<img src="accordanalyst-banner.svg"><br>
### Portfolio · Resume · Case Studies

*The portfolio site of Alexis Kelly — Business Operations Analyst*

![Status](https://img.shields.io/badge/status-live-6E1F2C?style=for-the-badge&labelColor=0B0B0F)
![Live Site](https://img.shields.io/badge/site-accordanalyst.com-3B5FE0?style=for-the-badge&labelColor=0B0B0F)
![Built With](https://img.shields.io/badge/built%20with-HTML%20%2F%20CSS%20%2F%20JS-4A2F6B?style=for-the-badge&labelColor=0B0B0F)
![Hosted On](https://img.shields.io/badge/hosted%20on-GitHub%20Pages-9E2A3D?style=for-the-badge&labelColor=0B0B0F)

</div>

---

## 🗂️ What's in this repo

This repository powers **[accordanalyst.com](https://www.accordanalyst.com/)** — a portfolio site, a standalone resume page, and four live interactive case studies. No frameworks, no build step — just hand-built HTML/CSS/JS, deployed straight through GitHub Pages.

```
portfolio/
├── index.html                  ← Home / Portfolio
├── resume.html                 ← Full résumé (Experience, Skills, Education, Volunteer)
├── projects.html               ← Full project catalog (all case studies, one page)
├── privacy-policy.html         ← Legal (store.accordanalyst.com)
├── terms-of-service.html       ← Legal (store.accordanalyst.com)
├── CNAME                       ← Custom domain config
├── robots.txt
├── ai-blocker.js                ← Site defense script (see Foxglove 🦊)
├── update-blocklist.py
│
└── projects/
    ├── intl-freight-audit.html
    ├── revenue-reconciliation.html
    ├── revenue-anomaly-detector.html
    ├── freight-audit-dashboard.html
    └── thumb/                   ⚠️ note: singular "thumb", not "thumbs"
        ├── intl-freight-audit.svg
        ├── revenue-reconciliation.svg
        ├── revenue-anomaly-detector.svg
        └── freight-audit-dashboard.svg
```

---

## 🍷 Design system — Ledger Noir

The entire site runs on a single visual identity: **Ledger Noir** — near-black and ivory, with a single garnet/wine accent standing in for every highlight, link, and rule on the page. Slab-serif headings (Zilla Slab), clean body text (Inter), monospace for dates and labels (IBM Plex Mono). The mood is editorial and restrained — a ledger with taste, not a dashboard.

| Token | Role | Light mode | Dark mode |
|---|---|---|---|
| `--bg` / `--surface` | Page & card background | `#F7F3EE` ivory | `#0D0908` near-black |
| `--heading` / `--nav-bg` | Headings, nav bar | `#14100E` | `#0A0706` |
| `--accent` | Links, highlights, rules | `#7A1F2E` garnet | `#B33A4C` |
| `--accent2` | Secondary depth accent | `#3D1015` deep wine | `#7A1F2E` |

Full light/dark toggle is built in — the palette above simply re-maps depending on the reader's preference.

---

## 🎨 Palette credit

<div align="center">

<img src="https://img.shields.io/badge/-000000?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-12234F?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-1E3A8A?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-3B5FE0?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-6B7FE0?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-5B9BD9?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-4A2F6B?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-9E2A3D?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-6E1F2C?style=flat-square" width="40"/> <img src="https://img.shields.io/badge/-3D1015?style=flat-square" width="40"/>

</div>

The site's entire color direction traces back to a single reference: a still from **David Lynch's *Blue Velvet* (1986)** — deep blues and violet-blacks set against a wall of stage-curtain red — sourced from the Instagram account **[@colorpalette.cinema](https://www.instagram.com/colorpalette.cinema/)**. Ledger Noir is that palette distilled down to its two most editorial notes — the shadow and the wine — for something that reads as a printed ledger rather than a movie still, but the lineage starts there. Full credit to **Color Palette Cinema** for the original extraction.

---

## 🧵 Recent changes

- 🆕 Added a **"Currently Building"** section — teaser cards for three in-development, industry-adjacent tools (kept intentionally low-detail given overlap with current employer), plus a full open listing for **Foxglove**, a passion project seeking a technical collaborator.
- 🧭 Rebuilt the resume as its **own page**, separate from the portfolio — Home now stays focused on About + Portfolio + Building, while Résumé gets Experience, Skills, Education, and Volunteer.
- ⏳ Replaced the plain Experience list with a real **alternating icon-node timeline**.
- 🛠️ Added a **Technical Skills** section (Languages & Querying · Spreadsheets & BI · Data & Platforms) — moved to the top of the résumé, color-coded per category.
- 🖼️ Swapped raw spreadsheet screenshots for **custom-designed SVG infographics** on each Featured Project card — same real numbers, cleaner presentation, crisp at any size.
- 🐛 Fixed a recurring **dark-mode contrast bug**: card headers were pulling their background from a token meant for text color, which flipped light in dark mode and made titles unreadable. Fixed across the homepage, the project catalog, and all four case studies.
- 📐 Fixed a **thumbnail cropping bug** — image containers now lock to the graphic's real aspect ratio instead of a fixed height, so nothing gets cut off on narrow cards.
- ✍️ Updated hero copy, marquee text, and title to **"Business Operations Analyst"**; broadened the "Let's connect" role list beyond fintech/freight to Data Analyst–oriented titles.
- 🧹 Removed the redundant "accordanalyst.com" line from the hero on every page.
- 📄 Surfaced **`projects.html`** — a full case-study catalog that existed but had no working link into it.
- 📄 Added a print-ready, Ledger Noir–styled **resume PDF** matching the site's own design language.

---

## ⚠️ Known gotchas (read before you redeploy)

- **Folder name is `thumb`, singular.** If you ever recreate this structure from scratch, match that exactly — `thumbs` (plural) will silently 404 every card image (ngl, this was both the funniest and most infuriating part of this process).
- **GitHub Pages → Settings → Actions → General → Workflow permissions** must be set to **"Read and write permissions."** If it's read-only, the `build` job can succeed while `deploy` fails, and the live site will look unchanged even after a successful-looking push.
- **DNS is on Porkbun**. I honestly bought it on there because: it's cute, it's cheap and when you press the butt on the pig it goes "oink oink".

---

## 🧰 Tech stack

`HTML5` · `CSS3 (custom properties, no framework)` · `Vanilla JavaScript` · `D3.js` (Revenue Anomaly Detector, Recovery Dashboard) · `React` (Compliance Lens, LedgerLens — in progress, not in this repo) · Google Fonts

---

## 📬 Contact

**Alexis "Zaira" Kelly**
[alexis@accordanalyst.com](mailto:alexis@accordanalyst.com) · [LinkedIn](https://linkedin.com/in/accordanalyst) · [accordanalyst.com](https://www.accordanalyst.com/)

<div align="center">

*Open to Data Analyst, Business Intelligence Analyst, and Data & Insights Analyst roles · Remote-friendly, async-first*

</div>
