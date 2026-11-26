# Poster design system (26 Nov 2026)

Code: `bin/typography.py` (functions `block`, `ink`, `paper`, `apply`; run it directly to build the sample sheet).
Sample output: `~/prototypes/posters/ds1/`. Only free OFL fonts, installed locally in `~/books/fonts/`.

## BLACK line (engraving on black)
Near-black paper with grain. Greyish-white letters. No bounce. Illustration on top, text below, left-aligned.

| Role | Font | Treatment |
|---|---|---|
| H1 title | Della Respira thickened OR Young Serif | Della: thickened horizontally only, letters tight, slight compression |
| H2 subtitle | Della Respira thin | 30% of the H1 height, one line |
| H3 label | Della Respira thin, widely spaced capitals | 15% of the H1 height, above the H1 |

## SEVENTIES line (red on cream)
Cream paper with specks. Brick red. H1 letters bounce and turn a little, wavy baseline, worn ink. Text on top, centred, illustration below.

| Role | Font | Treatment |
|---|---|---|
| H1 title | Fraunces black OR Young Serif OR Della Respira thickened | with bounce, spin and wave |
| H2 subtitle | Fraunces semi OR calm Young Serif | no bounce, red |
| H3 label | Della Respira thin, spaced | no bounce, near black |

Of the 6 variants of the type4 study: a-young, b-della-bold and d-fraunces-black became H1; e-fraunces-semi and f-young-no-bounce became H2; c-della-thin became H3.

## Rules
- Title always drawn in code (correct spelling, same lettering across the collection, change the phrase or language without generating the image again). GPT only draws the illustration, with no text.
- One line per poster. Do not mix Black and Seventies in the same poster.
- Our own phrases. No author names. No promise of results.
- AI illustration: declared when listed on Etsy; on the social networks the carousel engine labels every post as AI.

## Text effects (`bin/effects.py`, 26 Nov 2026)
All in code, no GPT. Sample output in `~/prototypes/posters/effects1/`.
- `circle()`: letters on an arc or around the whole turn (`full=True`), like a seal. Use with the H3.
- `bend(mask, mode, strength)`: `bridge` (arc up), `smile` (down), `bulge` (swells in the middle), `wave`. Use with the H1.
- `emboss()`: light letter with an offset dark shadow. Good for thick lowercase (Young Serif) on a colour background.
- Rule: at most one bend effect per poster, to keep it clean.

## Title position (26 Nov 2026)
- The title does not have to sit top centre. It can move: top, middle, bottom, left- or right-aligned,
  wherever the illustration leaves room. In the GPT prompt, ask for the empty zone where the title will go.
- Font quirks (for example Young Serif's old-style figures, where "11:11" reads as "ıı:ıı") stay as they are.

## Carousel format (`bin/carousel_art.py`)
- 3 message slides + 1 final CTA slide: "if this found you, pass it on." and 4 lines with our own icons:
  like, comment "WORD" below, share it with your bestie, save it for the hard days.
- Label "A MESSAGE FOR YOU n/4"; handle right below the title; title alternates top and bottom; dark veil behind the title.
- 1080x1350, exported as JPEG for the networks.
