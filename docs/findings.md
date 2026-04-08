# Findings and Recommendations

Full dataset: 15.65 million transaction and inventory rows across 6 source tables (2024 fiscal
year). 129 vendors, ~80 store locations, 6 product categories. All figures verified against raw
totals in `outputs/validation_report.txt`.

Gross Profit figures are period-aggregated, not period-matched. Sales in 2024 may draw from
inventory purchased in prior periods, so margin numbers are directionally reliable but not
equivalent to a formal COGS-based accounting margin. See [data_dictionary.md](data_dictionary.md)
for full field definitions and caveats.

---

## Finding 1 — Procurement Concentration Risk Is Material

**The top 10 vendors account for $210.3M of $321.9M in total procurement spend — 65.3% of
the entire purchasing budget.**

| Vendor | Procurement Spend | Cumulative % |
|---|---:|---:|
| DIAGEO NORTH AMERICA INC | $50,959,797 | 15.8% |
| MARTIGNETTI COMPANIES | $27,861,690 | 24.5% |
| JIM BEAM BRANDS COMPANY | $24,203,151 | 31.9% |
| PERNOD RICARD USA | $24,124,092 | 39.4% |
| BACARDI USA INC | $17,624,379 | 44.8% |
| CONSTELLATION BRANDS INC | $15,573,918 | 49.6% |
| BROWN-FORMAN CORP | $13,529,433 | 53.8% |
| ULTRA BEVERAGE COMPANY LLP | $13,210,614 | 57.9% |
| E & J GALLO WINERY | $12,289,608 | 61.8% |
| M S WALKER INC | $10,935,817 | 65.3% |

DIAGEO alone represents 15.8% of total procurement. A supply disruption, pricing renegotiation,
or contract change with any of these 10 vendors would affect the majority of purchasing volume
without requiring a major market event.

**Recommendation to Supply Chain Leadership:** initiate a vendor diversification review for the
top 5 vendors by spend. The goal should be reducing top-10 concentration below 55% over two
procurement cycles by qualifying alternative-source vendors for the highest-volume SKUs. Diageo's
$51M share is the most exposed single-vendor position.

---

## Finding 2 — Portfolio Gross Margin Is 28.8%, But Five High-Volume SKUs Are Structurally
Unprofitable

**Reconstructed gross margin across cost-basis matched rows: 28.8% ($130.0M GP on $451.6M
in sales).** This is directionally healthy, but five SKUs with $100K+ in annual sales are
running negative margins that are not explained by data artifacts — they reflect genuine cost
vs. pricing misalignment.

**Top 5 gross-profit contributors (SKU level):**

| Description | Vendor | Sales | Purchase Cost | Gross Profit | Margin |
|---|---|---:|---:|---:|---:|
| Jack Daniels No 7 Black | BROWN-FORMAN CORP | $5,101,920 | $3,811,252 | $1,290,668 | 25.3% |
| Capt Morgan Spiced Rum | DIAGEO NORTH AMERICA INC | $4,475,973 | $3,261,198 | $1,214,775 | 27.1% |
| Ketel One Vodka | DIAGEO NORTH AMERICA INC | $4,223,108 | $3,023,206 | $1,199,902 | 28.4% |
| Absolut 80 Proof | PERNOD RICARD USA | $4,538,121 | $3,418,304 | $1,119,817 | 24.7% |
| Tito's Handmade Vodka | MARTIGNETTI COMPANIES | $4,819,073 | $3,804,041 | $1,015,032 | 21.1% |

**Negative-margin SKUs with $100K+ in sales (potential pricing or sourcing issues):**

| Description | Vendor | Sales | Purchase Cost | Margin |
|---|---|---:|---:|---:|
| Buehler Znfdl Napa | MARTIGNETTI COMPANIES | $119,617 | $138,369 | **-15.7%** |
| Smirnoff Watermelon Vodka | DIAGEO | $100,067 | $106,106 | **-6.0%** |
| Ciroc Mango Vodka | DIAGEO | $164,084 | $173,953 | **-6.0%** |
| Crown Royal Vanilla | DIAGEO | $176,578 | $185,784 | **-5.2%** |
| Crown Royal Nrth Harvest Rye | DIAGEO | $113,966 | $115,712 | **-1.5%** |

**Recommendation to Category Management:** audit purchase price vs. selling price for the five
negative-margin SKUs. Buehler Znfdl Napa at -15.7% is the sharpest case — at this margin, the
distributor is effectively subsidising the sale. Either renegotiate the unit cost with MARTIGNETTI
COMPANIES or adjust the retail price. The four Diageo SKUs may reflect a promotional pricing
decision that was not offset by a cost concession.

---

## Finding 3 — Working Capital Is Concentrated in the Same Top-Vendor Tier

**Total unsold inventory value (cost basis): $15.60M. The top 10 vendors hold $10.12M of that —
64.9% of all unsold inventory exposure.**

| Vendor | Unsold Inventory Value | % of Total |
|---|---:|---:|
| MARTIGNETTI COMPANIES | $1,928,346 | 12.4% |
| DIAGEO NORTH AMERICA INC | $1,656,476 | 10.6% |
| ULTRA BEVERAGE COMPANY LLP | $1,475,999 | 9.5% |
| JIM BEAM BRANDS COMPANY | $1,136,391 | 7.3% |
| PERFECTA WINES | $915,644 | 5.9% |
| M S WALKER INC | $850,048 | 5.4% |
| PERNOD RICARD USA | $723,100 | 4.6% |
| WILLIAM GRANT & SONS INC | $502,618 | 3.2% |
| E & J GALLO WINERY | $486,889 | 3.1% |
| CONSTELLATION BRANDS INC | $448,593 | 2.9% |

**Highest unsold inventory SKUs:**

| Description | Vendor | Unsold Value | Sell-Through Rate |
|---|---|---:|---:|
| Smirnoff Traveler | DIAGEO | $169,786 | 91.9% |
| Johnnie Walker Black Label | DIAGEO | $144,338 | 89.8% |
| Johnnie Walker Red Label | DIAGEO | $123,291 | 91.8% |
| Tito's Handmade Vodka | MARTIGNETTI | $87,913 | 97.7% |
| Jack Daniels No 7 Black | BROWN-FORMAN | $79,624 | 97.9% |

Note: Smirnoff Traveler, Johnnie Walker Black, and Johnnie Walker Red all have sell-through rates
below 92% — meaningful unsold positions for high-volume SKUs. The Tito's and Jack Daniel's unsold
positions are comparatively small relative to their total purchase volumes (97–98% sell-through)
but appear here because of their sheer procurement scale.

There are also 5 vendors with unsold inventory exceeding 80% of their total procurement value.
These represent fully or almost-fully stalled product lines worth reviewing for return eligibility
or markdown.

**Recommendation to Inventory Management:** prioritise the Diageo Smirnoff and Johnnie Walker
SKU unsold positions for markdown or return negotiation — these are the largest single-SKU
unsold dollar positions. Separately, commission a targeted review of vendors with >80% unsold
procurement ratios; the small-vendor tail may represent ordering errors or discontinued products
that can be closed out.

---

## Finding 4 — Revenue Has a Sharp Q4/December Seasonal Peak; Purchasing Should Anticipate It

**Q4 sales ($131.1M) were 49.4% higher than Q1 ($87.7M). December alone ($52.3M) was 75.2%
above January ($29.9M).**

| Month | Monthly Sales | Index (Jan = 100) |
|---|---:|---:|
| January | $29,854,028 | 100 |
| February | $28,876,607 | 97 |
| March | $28,988,412 | 97 |
| April | $30,723,735 | 103 |
| May | $36,041,211 | 121 |
| June | $39,290,701 | 132 |
| July | $49,696,467 | 166 |
| August | $39,056,166 | 131 |
| September | $38,477,539 | 129 |
| October | $36,433,142 | 122 |
| November | $42,312,697 | 142 |
| **December** | **$52,312,248** | **175** |

The distribution is not symmetric: there is a summer peak (July at 166) and a sharp December
peak (175). February and March are the trough. The implication for procurement timing: purchase
orders for high-volume SKUs need to be placed 9–14 days (the observed average lead time) ahead
of these demand peaks, meaning August purchase orders for summer and mid-November purchase orders
for the December ramp.

**Recommendation to Procurement Planning:** build a rolling 12-month purchase order calendar
anchored to these seasonal indices. Given a 9.7-day average lead time and 13-day maximum observed,
buffer stock for the top 20 SKUs by volume should be ordered by the 15th of the prior month for
peak periods. A $3M+ swing between the trough (February) and the December peak means
under-stocking in Q4 translates directly to lost sales.

---

## Finding 5 — Delivery Performance Is Consistent but the Framework Is Operational

**Average lead time across 126 measurable vendors: 9.7 days (median 9.8 days, range 5.0–13.0
days). All 126 vendors met the 14-day OTIF SLA proxy. Zero negative lead-time rows in the
delivered dataset.**

This means the pipeline's vendor reliability tier framework — TIER_1_RELIABLE (≥95% OTIF),
TIER_2_ACCEPTABLE (≥80%), TIER_3_AT_RISK (<80%) — classifies all vendors as TIER_1 on this
dataset, producing no differentiation. That is not a code problem; it reflects the data. Two
interpretations are plausible: the source data may be cleaned or synthetic, or this distributor
genuinely operates with tightly managed vendor contracts.

The framework's value is as a repeatable baseline. Five vendors show the highest lead-time
variance, meaning delivery timing is less predictable even if still within the SLA:

| Vendor | Avg Lead Time | Lead Time Variance | Total POs |
|---|---:|---:|---:|
| ALISA CARR BEVERAGES | 7.6 days | 6.44 | 19 |
| ALTAMAR BRANDS LLC | 7.9 days | 6.09 | 40 |
| STARK BREWING COMPANY | 9.2 days | 5.81 | 12 |
| STAR INDUSTRIES INC. | 8.3 days | 5.44 | 13 |
| Circa Wines | 8.0 days | 5.39 | 43 |

Higher variance = less predictable receiving windows = harder to plan around, even when average
lead time is short. ALTAMAR BRANDS LLC at 40 POs with variance 6.09 is the most operationally
relevant: frequent ordering combined with unpredictable timing.

**Recommendation to Operations:** apply tighter buffer stock or a minimum-order-cycle rule for
the 5 highest-variance vendors. For period-over-period comparison in future years, the OTIF
framework and 14-day SLA threshold are already instrumented and will produce tier differentiation
if supply chain conditions change.

---

## Summary of Recommendations

| Priority | Recommendation | Owner | Estimated Impact |
|---|---|---|---|
| 1 | Audit and reprice 5 negative-margin SKUs (led by Buehler Znfdl Napa at -15.7%) | Category Management | Immediate margin recovery on ~$674K in annual sales |
| 2 | Initiate vendor diversification review for top 5 by spend | Supply Chain Leadership | Reduce concentration risk from 65.3% to <55% of procurement |
| 3 | Markdown or return-negotiate top 3 unsold Diageo SKUs ($437K tied up) | Inventory Management | $437K+ in freed working capital |
| 4 | Build Q4/December procurement buffer calendar anchored to seasonal index | Procurement Planning | Avoid stock-outs during 49% seasonal revenue uplift |
| 5 | Apply buffer stock rule for 5 highest-variance vendors | Operations | Reduce receiving-window uncertainty on 127+ annual POs |
