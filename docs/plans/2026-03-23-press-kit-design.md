# A-U.Supply Press Kit — Design Specification

## Overview

Two press kit PDFs styled as industrial manufacturer documentation. The format is applied with deadpan sincerity — no winking, no overt satire, no spelled-out irony. Someone encountering these documents should genuinely wonder whether they come from a real industrial company, a training materials vendor, or some kind of clerical error. The confusion is the point. The documents should be indistinguishable from actual industrial literature except that the product happens to be audio.

### Deliverables

- `press-kit/au-supply-press-kit.html` → `press-kit/au-supply-press-kit.pdf`
- `press-kit/complete-double-album-press-kit.html` → `press-kit/complete-double-album-press-kit.pdf`
- `press-kit/assets/` — high-res images for media use
- Generated via Chrome headless `--print-to-pdf`

### Source Documents

- `docs/au-supply-complete-reference.md` — label, catalog, members, philosophy
- `docs/albums/complete-double-album-reference.md` — track-by-track double album reference

---

## Visual Design System

### Typography
- **Primary**: Monospace (Courier New or similar system monospace). All body text, tables, labels.
- **Headings**: Monospace, uppercase, letterspaced. No decorative fonts.
- **Accent**: Sparse use of bold for field labels. No italics except for album titles per convention.

### Color Palette
- **Background**: White (#fff) or very light warm gray (#f5f4f0)
- **Primary text**: Near-black (#1a1a1a)
- **Secondary text / labels**: Medium gray (#666)
- **Accent**: Amber (#b8860b) — used sparingly for rule lines, stamps, and form field borders
- **Warning accent**: Muted red (#8b0000) — used only on the double album kit for classification markings

### Layout
- **Page size**: US Letter (8.5 × 11in)
- **Margins**: Generous (1in+). Industrial spec sheets have lots of whitespace.
- **Grid**: Single column with occasional two-column sections for side-by-side specs
- **Tables**: Plain, ruled. Thin borders. No zebra striping. Header rows in uppercase.
- **Borders**: Thin solid lines. Dotted lines for form fields. No rounded corners.
- **Page numbers**: Bottom right, monospace, formatted as "Page X of Y"
- **Headers**: Repeated company identifier top-right of each page: "A-U.SUPPLY — AUDIO UNITS DIVISION"

### Graphic Elements
- **Logo**: cheeze-bourger2.png treated as corporate wordmark. Placed at actual size or scaled proportionally. No special framing — just dropped in like a company logo on letterhead.
- **Album art**: Presented as product photography. Displayed at moderate size with a thin border and a caption underneath (product code, dimensions, date).
- **Stamps**: "APPROVED," "REVISION 01," "FOR DISTRIBUTION" — monospace text in amber, rotated slightly, placed sparingly. These should look like rubber stamps on a document, not graphic design elements.
- **Rules**: Thin horizontal rules to separate sections. Double rules for major divisions.
- **No icons, no emoji, no decorative elements.** The document's austerity IS the design.

---

## Press Kit 1: A-U.Supply — Company Overview

### Cover Page

```
A-U.SUPPLY
AUDIO UNITS DIVISION

Company Profile & Product Catalog
Document No: AU-REF-2026-001
Revision: 01
Date of Issue: 2026-03-23

[cheeze-bourger2.png]

CLASSIFICATION: General Distribution
```

No tagline on the cover. Clean. The tagline appears inside.

### Section 1: Company Profile

Formatted as a form with field labels and values:

- **Registered Name**: Audio Units Supply
- **Operating As**: A-U.Supply / A-U / AU
- **Established**: Under review (earliest records: 2009; first production run: 2015; initial catalog: 2020)
- **Facilities**: Minneapolis, MN; San Francisco / Oakland, CA; Canadian heartland
- **Contact**: ausupply000@gmail.com
- **Web**: https://a-u.supply
- **Motto**: "Floating in a mire of semantical truzzles, so you don't have to."

Brief paragraph (2-3 sentences) describing the operation. Drawn from reference doc §1.2 but in industrial-catalog language. No adjectives like "experimental" or "avant-garde." Describe what they do, not what genre they are.

### Section 2: Personnel

Four entries. Each formatted as:

```
DEPARTMENT: [title]
PERSONNEL: [name]
CLASSIFICATION: [role description in industrial language]
REMARKS: [fabricated quote — dry, in character]
```

Names and roles from reference doc §2.1:
- number 4 — Superintendent, Final Assembly
- NoNameSteak — Foreman, Robot Ranch / Texture Division
- Ancients — Chief Vocal Supply
- MCA — Director, Philosophy & Signal / Singer-Songwriter

Additional note: "Total personnel: 4 (official). Extended personnel: unconfirmed. Alias rotation in effect."

No headshot images. Personnel photos: "NOT AVAILABLE — SEE POLICY AU-HR-003."

### Section 3: Product Catalog

The full discography from reference doc §1.3 presented as a product table.

Columns:
- **Item No.** (sequential)
- **Product Code** (catalog number or generated code)
- **Product Name** (release title)
- **Manufacturer** (artist)
- **Date of Manufacture**
- **Units** (track count)
- **Runtime**
- **Distribution Channel**

Below the table: album cover images (the 375×375 Bandcamp covers, the AEDAS and THT high-res art) displayed as product photography with captions.

### Section 4: Production Infrastructure

The bots and tools described as production line equipment:

- **Line 1 — MIDI Generation** (midi-bot): Daily output of 4 units. Neural network-assisted (Magenta.js). Scales sourced globally.
- **Line 2 — Audio Collage** (glottisdale): Syllable-level segmentation and reassembly. Batch processing via GitHub Actions.
- **Line 3 — Vocal Mapping** (hymnal-bot): MIDI-to-vocal pipeline. Magenta.js extension module.
- **Line 4 — Prompt Generation** (surreal-prompt-bot): Daily surrealist drawing prompts. LLM-assisted (Groq/Llama).
- **Line 5 — Playlist Assembly** (muzzik-bot): YouTube playlist maintenance. Daily intake from Slack channel.
- **Line 6 — Title Filtration** (song-titles-bot): Song title quality assurance via HF Inference API.

Standalone tools section:
- **BadTV**: TV News Archive word-level extraction and audio collage. Rust.
- **youboob**: YouTube stem separation (HTDemucs). Rust.

### Section 5: Distribution Network

Table format:
- **Bandcamp** — Primary warehouse (recent releases, high-resolution formats)
- **Archive.org** — Long-term storage (2020 catalog)
- **SoundCloud** — Auxiliary storage (~60 units, session/sketch material, 2014–present)
- **YouTube** — Audiovisual distribution (singles, compilations, double album)

### Section 6: Associated Entities

Brief listing of known aliases/projects from reference doc §1.4. Formatted as a supplier/subcontractor directory. No explanations — just names, product associations, and "RELATIONSHIP: See purchasing department."

### Section 7: External Partnerships

- Internet Archive
- Vintage Computer Festival Midwest
- Sunny Flea Market
- ECCC

One line each. No elaboration.

### Back Cover

```
A-U.SUPPLY — AUDIO UNITS DIVISION
Document No: AU-REF-2026-001

ausupply000@gmail.com
https://a-u.supply

"Your only choice will be between a goat's ass and the face of god."
```

---

## Press Kit 2: Complete — Double Album Product Bulletin

### Cover Page

```
A-U.SUPPLY — AUDIO UNITS DIVISION

PRODUCT BULLETIN
Classification: New Release

Product: Law Bale Straw Wonder / Tomato Sink Cloud Tag
Manufacturer: Complete
Batch No: AU-2026-DA-001
Date of Manufacture: 2026-03-22
Document No: AU-PB-2026-001

[THT cover2.jpg — large, centered]

DOUBLE UNIT — SHIPS AS TWO (2) ITEMS
```

### Section 1: Product Specifications

Form-style layout:

- **Product Name**: Law Bale Straw Wonder / Tomato Sink Cloud Tag
- **Manufacturer**: Complete
- **Date of Manufacture**: 2026-03-22
- **Total Runtime**: ~62:18
- **Unit Count**: 2
- **Format**: Digital (YouTube)
- **Distribution**: https://www.youtube.com/@a-u.supply674

**Unit A — Law Bale Straw Wonder**
- Runtime: 34:10
- Components: 11
- Character: Industrial labor, physical strain, found audio, spoken word, satirical pivot, pastoral/neurological juxtaposition

**Unit B — Tomato Sink Cloud Tag**
- Runtime: 28:08
- Components: 13
- Character: Fragmentation, infrastructure failure, psychological dissolution, confessional disclosure, resigned conclusion

### Section 2: Bill of Materials — Unit A

Table with columns:
- **Item** (1–11)
- **Part Name** (track title)
- **Timestamp** (start–end)
- **Duration**
- **Material Composition** (sonic palette described in materials language — no jokes, just dry technical description: "industrial drone substrate, repetitive vocal element, ambient bed")
- **Function** (one line from the reference doc's thematic function, compressed)

All 11 tracks from `docs/albums/complete-double-album-reference.md` Disc 1.

### Section 3: Bill of Materials — Unit B

Same format, all 13 tracks from Disc 2.

For "231122_0320 Giant Casio" — no special callout. It gets the same dry treatment as every other line item. The content speaks for itself.

### Section 4: Material Safety Data

The thematic concerns from both reference docs, presented as material properties and handling notes. Played completely straight:

- **Primary Composition**: Found audio, industrial drone, spoken word, lo-fi guitar, synthesizer
- **Secondary Composition**: Sampled instructional material, broadcast fragments, field recordings
- **Processing Method**: Progressive degradation (multi-pass resampling, bounce-and-degrade cycles)
- **Fidelity Range**: Low to very low (by specification)
- **Known Properties**: Semantic satiation, non-hierarchical sequencing, abrupt tonal shifts
- **Recurring Compounds**: Heat, labor, consumption, depersonalization, Americana (degraded), infrastructure failure, chrematistics
- **Storage**: No special requirements. Content stable at any resolution.

### Section 5: Manufacturer Profile

Brief section on Complete. 4 personnel. Roles listed (from reference doc §2.1). Prior product history (How How Things are Made are Made, Em). No quotes in this kit — just the facts as presented in industrial language.

Note: "For full manufacturer profile, see Document No: AU-REF-2026-001."

### Section 6: Cross-Reference Matrix

The motif cross-reference table from the double album reference doc (§4), presented as a parts compatibility / cross-reference matrix. Same data, industrial framing.

### Section 7: Related Products

- Semi-Truck Driver (standalone, 2023) — "Pre-release sample. Now incorporated into Unit B, Item 12."
- Pathos for Bathos (standalone, 2024) — "Pre-release sample. Now incorporated into Unit A, Item 11."
- A-U Quality Track Supply (compilation, 2024) — "Contains material from this manufacturer and associated suppliers."

### Back Cover

```
A-U.SUPPLY — AUDIO UNITS DIVISION
Document No: AU-PB-2026-001

FOR INQUIRIES: ausupply000@gmail.com
PRODUCT CATALOG: https://a-u.supply

[AEDAS-Album.jpg — moderate size]
```

---

## Assets Directory

`press-kit/assets/` contains:

| File | Source | Description |
|------|--------|-------------|
| cheeze-bourger2.png | img/ | Company wordmark |
| AEDAS-Album.jpg | img/ | High-res album art (8382×8382) |
| THT cover2.jpg | img/ | High-res cover art (4871×4871) |
| Em Complete Cover 2.jpg | img/ | *Em* album cover |
| au_erkind-nos.jpg | img/ | *Erkind NOS* cover |
| au_how-how-things-are-made-are-made.jpg | img/ | *How How Things are Made are Made* cover |
| au_immelerria.jpg | img/ | *~~Immelerria~~* cover |
| A Deper[ ]alized Ratio.jpg | img/ | *A Deper[ ]alized Ratio* cover |
| teashirt.JPG | img/ | Merch photography |
| channels4_profile.jpg | img/ | YouTube profile image |

---

## Implementation Notes

- HTML + CSS → Chrome headless `--print-to-pdf`
- Print CSS: `@page` rules for margins, page breaks, headers
- Images referenced with relative paths from press-kit/
- Stamp effects: CSS `transform: rotate()` + amber color + border
- No JavaScript needed — pure HTML/CSS documents
