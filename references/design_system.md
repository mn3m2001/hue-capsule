## 7. Mandatory PDF Design System & Academic Presentation Standards

All HTML templates compiled to PDF deliverables in any HUE course MUST strictly adhere to the **Optoelectronics Master Standard** (`El_Zaytouna_Opto_Master_V7_Priority.html`).

### Core Presentation Rules:
1. **Zero Monospace Terminal Blocks:** NEVER use dark backgrounds, console terminal styling, ASCII-art boxes, or fixed-width code font blocks (`monospace`, `Courier`, `JetBrains Mono`) for physical laws, formulas, or step-by-step problem derivations.
2. **Academic Serif Typography for Mathematics:**
   - Math equations and derivations must use `font-family: 'Cambria Math', 'Times New Roman', serif;`.
   - Variables are italicized (`<span class="var">x</span>`).
   - Units use clean sans-serif typography (`<span class="unit">W/m·K</span>`).
3. **True Vertical Fractions (Flex Columns):**
   - All divisions, ratios, and fractions MUST render as vertical stacked numerator and denominator:
     `<div class="frac"><span class="num">Numerator</span><span class="den">Denominator</span></div>`
   - CSS rules:
     ```css
     .frac { display: inline-flex; flex-direction: column; vertical-align: middle; text-align: center; padding: 0 4px; }
     .num { border-bottom: 1.5px solid #1e293b; padding-bottom: 2px; }
     .den { padding-top: 2px; }
     ```
4. **Step-by-Step Mathematical Flow:**
   - Use bold mathematical connective symbols:
     - `<span class="sym-since">&because;</span>` (Since)
     - `<span class="sym-therefore">&there4;</span>` (Therefore)
     - `<span class="red-arrow">&rArr;</span>` (Implies / yields)
   - Final answers enclosed in an explicit green badge block:
     `<div class="ans"><b>Final Answer:</b> ...</div>`
5. **Front-Loaded Verbal Directives Card (`.audio-card`):**
   - The very first card under the document header MUST be an alert card displaying all oral directives extracted from primary lecture recordings and revision sections (exam duration, question count, exclusions, grading rubrics, calculator rules).
6. **Card & Badge Architecture:**
   - Every problem, law, and theory item is encapsulated inside a `.card` container with:
     - `.q-head`: Title and badge group (`.badge-src`, `.badge-rev`, `.badge-prob`, `.badge-count`, `.badge-marks`).
     - `.why`: Amber box for physical intuition and Egyptian-Arabic explanation.
     - `.q-box`: Formal English problem statement.
     - `.math-block`: Clean serif derivation block with vertical fractions.
7. **Print & Page Break Safeguards:**
   - Enforce `page-break-inside: avoid; break-inside: avoid;` on all cards, formula boxes, and intuition blocks to prevent awkward mid-derivation page breaks in headless Chrome/Edge PDF rendering.

