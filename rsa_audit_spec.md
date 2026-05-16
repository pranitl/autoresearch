# FirstLight RSA Audit Spec — 2026-03-29

Current champion score: 90/100
This file is a working copy of the March 29 RSA audit for a document-first specsearch loop.
The loop may only edit the `### Editable Challenger` block inside one active ad-group section per round.
All other content is locked audit evidence or reference context.

1. Locked Audit Context

## Executive Read

- The active reset learning surface is mainly `Private Home Care Near Me` and `Core Non-Medical Home Care`.
- `Companion / Private Caregiver` has now been paused as cleanup because it was an enabled shell with all keywords paused.
- New replacement RSAs were created for the two broad live reset groups using the service-hub URL instead of the homepage.
- Conversion counts are attribution-limited because call attribution is known-broken; use clicks, spend, CTR, ad-strength, query quality, and form/call corroboration more heavily than raw conversion totals.

## Current Winners / Best Incumbents

- **Caregiver Services** — incumbent winner: ad `797661377482` | status `ENABLED` | 123 impr / 10 clicks / 8.13% CTR / $25.78 / 0.0 conv | URL `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- **City-Specific** — incumbent winner: ad `797718501022` | status `ENABLED` | 83 impr / 5 clicks / 6.02% CTR / $9.99 / 0.0 conv | URL `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/`
- **Companion / Private Caregiver** — incumbent winner: ad `799582490762` | status `ENABLED` | 119 impr / 11 clicks / 9.24% CTR / $57.10 / 0.0 conv | URL `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/companion-care/`
- **Core Non-Medical Home Care** — incumbent winner: ad `797661377188` | status `ENABLED` | 715 impr / 50 clicks / 6.99% CTR / $190.70 / 1.0 conv | URL `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/`
- **Private Home Care Near Me** — incumbent winner: ad `799582490639` | status `ENABLED` | 330 impr / 48 clicks / 14.55% CTR / $334.21 / 0.0 conv | URL `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/`
- **Problem-Aware Parents** — incumbent winner: ad `797739735353` | status `ENABLED` | 45 impr / 3 clicks / 6.67% CTR / $2.48 / 0.0 conv | URL `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/`

## URL Grounding Map For Judge Loop

| Ad Group | Strategic Role | Recommended URL | Why |
|---|---|---|---|
| Private Home Care Near Me | ACTIVE RESET CORE | `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/` | Broad but high-intent service discovery; service hub is cleaner than the homepage. |
| Core Non-Medical Home Care | ACTIVE RESET CORE | `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/` | Broad commercial home-care intent should land on the service library, not the generic homepage. |
| Companion / Private Caregiver | PAUSED CLEANUP SHELL | `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/companion-care/` | Companion intent maps cleanly to the Companion Care page. |
| Caregiver Services | LEGACY PAUSED | `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/` | Only reuse with explicit reactivation. |
| City-Specific | LEGACY PAUSED | `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/` | If ever revived, use a more specific city/service page plan. |
| Problem-Aware Parents | LEGACY PAUSED | `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/` | Only revisit after reset stability and stronger attribution. |

## Site Service Library

- Service Hub: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- Personal Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/personal-care/`
- Companion Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/companion-care/`
- Respite Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/respite-care/`
- Dementia Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/dementia-care/`
- Veteran Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/specialty-care/veteran-care/`
- Disability Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/specialty-care/disability-care/`
- Family Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/specialty-care/family-care/`
- Live-In Care: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/specialty-care/live-in-care/`
- Travel Companion: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/specialty-care/travel-companion/`

## Judge-Loop Inputs To Carry Forward

Use the inputs in this section as soft context for the judge loop.
They are intended to improve tie-breaking, drift detection, and idea quality, not to force every challenger toward the same wording or asset mix.
Only explicit hard constraints elsewhere in the program and rubric should behave like true gates.

### Search-term evidence to weight heavily

- Tier 1 / strongest commercial intent: `private duty home care`, `private duty caregiver near me`, `private caregiver near me`, `home care agency near me`, `non medical home care`
- Tier 2 / short leash: `caregiver services`, `adult home care`, `home care services`, `in home care services`, `companion care`, `caregiver needed nearby`
- Current sparse-but-useful evidence:
  - `private duty home care` remains one of the clearest live core terms in `Core Non-Medical Home Care`
  - `caregiver services` and `adult home care` keep showing spend without corroborating signal, so treat them as mixed-to-weak unless backed by form/call quality
  - `home care boston ma` is still the main city-modified survivor in the paused geo bucket
- Search terms matter more than raw conversion totals right now because call attribution is still understated.

### Current negatives / junk patterns already known

- Known negatives already applied during reset work: `home health aide`, `privatus care`, `assisting hands`, `visiting nurses`, `caregiver apps`, `regional home care`, and shared exact negative `[caregiver near me]`
- Patterns to keep blocking even if they occasionally click:
  - competitor-brand traffic
  - clinical / home-health / therapy intent
  - assisted-living / facility / nursing-home intent
  - job-seeker / hiring / application intent
  - very broad research traffic with weak private-pay intent
- If a new RSA draft leans into any of those buckets, it is probably contaminating the learning surface.

### Google quality labels / performance signal available in this export

- This export includes ad-level strength buckets from Google Ads: `EXCELLENT`, `GOOD`, `POOR`
- It does not currently include per-asset label breakout (`Best` / `Good` / `Low`) at headline/description level
- Most useful current examples:
  - `Private Home Care Near Me`: incumbent ad `799582490639` = `EXCELLENT`
  - `Core Non-Medical Home Care`: control ad `797661377188` = `GOOD`; sharper challenger `799582490765` = `EXCELLENT`
  - `Companion / Private Caregiver`: incumbent `799582490762` = `EXCELLENT`; weaker generic ad `797661383887` was a `POOR` cleanup target and has been paused
- Until asset-level labels are available, use ad strength plus clickthrough and search-term fit as the live Google-side quality proxy.

### Approved differentiator truth set

- No Weekly Minimums
- Licensed & Insured
- Family-Owned / Local Family-Owned
- Local Boston NW Team / Serving Boston Northwest communities
- Free Consultation / Free Care Assessment
- Flexible Care Plans / Flexible Scheduling
- Background-Checked, Trained, Supervised caregivers
- VA Benefits Assistance
- Call-first / talk-to-a-care-advisor / responsive local team framing

### Phrases / angles to avoid in new RSA drafts

- Too soft: vague sentimental fluff like "become like family" as the main claim
- Too clinical: home health, nursing, therapy, medical or clinical-care framing
- Too broad: `senior care services`, generic elder-care framing with no private-pay or in-home anchor
- Too job-seeker-y: `caregiver needed`, hiring / jobs / application language
- Too ambiguous: generic caregiver language that weakens the private-pay/home-care signal unless paired with stronger context

### Historical lead-quality hints to preserve

- Best-fit themes: `private duty home care`, `private caregiver near me`, `private duty caregiver near me`, `non medical home care`, `home care agency near me`
- Weak/mixed themes: `caregiver services`, `adult home care`, `home care services`
- Shortest leash term: `caregiver needed nearby`
- Explicitly blocked generic leakage: `caregiver near me` is blocked as a shared exact negative so `private caregiver near me` can stay active without reopening junkier adjacency
- When attribution is incomplete, these qualitative priors should break ties before raw conversion math does.

2. Core Non-Medical Home Care

### Locked Evidence

- Ad Group ID: `193039051603`
- Status: `ENABLED`
- Role in campaign: **ACTIVE RESET CORE**
- Purpose: Capture broad but still commercially relevant private-duty / non-medical home-care demand without reopening junk-heavy broad themes.
- Intent tier: Tier 1 core with some controlled adjacency
- Approved recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- URL reasoning: Broad commercial home-care intent should land on the service library, not the generic homepage.
- Keyword reality: 6 enabled / 14 paused / 4 enabled keywords with impressions in the last 30d
- Top keyword evidence:
  - `private duty home care` (PHRASE, ENABLED) — 358 impr / 27 clicks / $154.59 / 0.0 conv
  - `senior care services` (PHRASE, PAUSED) — 313 impr / 24 clicks / $84.97 / 0.0 conv
  - `in home care services` (PHRASE, PAUSED) — 290 impr / 16 clicks / $50.22 / 1.0 conv
  - `home care services` (PHRASE, PAUSED) — 159 impr / 7 clicks / $21.09 / 0.0 conv
  - `home care agency` (PHRASE, PAUSED) — 99 impr / 4 clicks / $8.24 / 0.0 conv
  - `elderly home care` (PHRASE, PAUSED) — 60 impr / 1 clicks / $7.92 / 0.0 conv
  - `adult home care` (PHRASE, PAUSED) — 58 impr / 9 clicks / $52.75 / 0.0 conv
  - `senior home care` (PHRASE, PAUSED) — 55 impr / 5 clicks / $39.26 / 0.0 conv
- Locked live comparators:
  - RSA `797661377188` — `ENABLED` — `GOOD` — homepage URL — 715 impr / 50 clicks / 6.99% CTR / $190.70 spend / 1.0 conv
    - Headlines:
      - Home Care That Feels Right
      - Trusted Senior Care
      - In-Home Care Services
      - Care On Your Terms
      - Compassionate Home Help
      - Senior Care You Can Trust
      - Professional Home Care
      - Caring For Boston NW
      - FirstLight Home Care
      - No Weekly Minimums
      - Start With What You Need
      - Licensed & Insured
      - Family-Owned Agency
      - Free Consultation Today
      - We're Here For You
    - Descriptions:
      - Home care that fits your life. From a few hours weekly to daily support. No minimums.
      - Compassionate caregivers who treat your family like their own. Serving Boston NW.
      - Professional, reliable home care from a family-owned agency. Free consultation today.
      - Your loved one deserves care that adapts to their needs. Flexible plans, caring people.
  - RSA `799582490765` — `ENABLED` — `EXCELLENT` — homepage URL — 293 impr / 27 clicks / 9.22% CTR / $153.80 spend / 0.0 conv
    - Headlines:
      - Non-Medical Home Care
      - Private Duty Home Care
      - FirstLight Home Care
      - Private-Pay Care At Home
      - No Weekly Minimums
      - Talk To A Care Advisor
      - In-Home Care Services
      - Licensed & Insured
      - Local Boston NW Team
      - Adult Home Care
      - Trusted Local Caregivers
      - Care Starts This Week
      - Home Care For Seniors
      - Help For Aging Parents
      - Free Consultation Today
    - Descriptions:
      - Private-pay non-medical home care from a trusted local team in Boston Northwest.
      - From a few hours to daily support, get flexible in-home care without weekly minimums.
      - Talk with a care coordinator today about private duty home care for your loved one.
      - Clear next steps, caring people, and home care that feels personal, not corporate.
  - RSA `802660468725` — `ENABLED` — `PENDING` — service-hub URL — 0 impr / 0 clicks / 0.00% CTR / $0.00 spend / 0.0 conv
    - Headlines:
      - Non-Medical Home Care
      - Private Duty Home Care
      - In-Home Care Services
      - FirstLight Home Care
      - Private Pay Care At Home
      - Local Boston NW Team
      - No Weekly Minimums
      - Talk To A Care Advisor
      - Adult Home Care Services
      - Trusted Local Caregivers
      - Help For Aging Parents
      - Flexible Care Plans
      - Care Starts This Week
      - Licensed & Insured
      - Free Consultation Today
    - Descriptions:
      - Private-pay non-medical care from a trusted local team.
      - See personal, companion, respite, dementia, and live-in care.
      - From a few hours to ongoing help, with no weekly minimums.
      - Talk with a care coordinator for clear next steps today.

### Locked Notes

- Only the `### Editable Challenger` block below may change.
- Keep the fixed recommended URL on the service hub.
- Judge this challenger against both live baselines `797661377188` and `799582490765`.
- Optimize for high-intent private-pay clicks, not generic traffic.

### Editable Challenger
Hypothesis: Combining the strongest proven elements—top private-duty keyword anchors, explicit private-pay and family-owned local signals, and the highest-CTR trust and urgency signals—creates the most promotion-worthy synthesis challenger. Lead with what Tier 1 keywords signal: private-pay intent, professional caregivers, and flexible service delivery from a local accountable team.
Target query themes:
- private duty home care
- non-medical home care
- in home care services
- adult home care
Fixed recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
Headlines:
- Private Duty Home Care
- Non-Medical Home Care
- In-Home Care Services
- Private-Pay Care At Home
- FirstLight Home Care
- Family-Owned Boston NW Care
- No Weekly Minimums
- Talk To A Care Advisor
- Background-Checked Caregivers
- Licensed & Insured
- Flexible Care Plans
- Private-Pay Home Care
- Get Care This Week
- Adult Home Care Services
- Start With A Free Consult
Descriptions:
- Private-pay home care from a family-owned local team. Serving Boston Northwest.
- See companion, personal care, respite, dementia, and live-in support—no weekly minimums.
- Flexible in-home care plans from background-checked caregivers. Start with what you need.
- Ready to explore care options? Talk with a local coordinator today—free consultation.
Why this should beat current live ads:
- Leads with the top-performing keyword `private duty home care` as the primary headline anchor.
- Replaces generic "Family-Owned Local Team" with "Family-Owned Boston NW Care" for tighter local specificity.
- Adds explicit "Private-Pay Home Care" headline to strengthen the commercial-intent signal for top private-pay and private-duty search queries.
- Removes redundant "Care For Aging Loved Ones" (duplicate with "Care For Aging Parents") and adds "Private-Pay Home Care" for better keyword variety.
- Adds "Get Care This Week" to better match the urgency theme already proven in the EXCELLENT-rated RSA.
- Changes "Free Consultation Today" to "Start With A Free Consult" for clearer first-step framing.
- Combines the EXCELLENT-rated RSA's CTR language with the family-owned trust signal from the GOOD-rated incumbent.
- Service-hub URL provides cleaner landing for service-discovery intent compared to homepage.
- Description set balances explicit service enumeration with private-pay and flexibility messaging.

3. Private Home Care Near Me

### Locked Evidence

- Ad Group ID: `193283912533`
- Status: `ENABLED`
- Role in campaign: **ACTIVE RESET CORE**
- Purpose: Capture highest-intent local private-pay near-me demand during the March 8 reset.
- Intent tier: Tier 1 core
- Approved recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- URL reasoning: Broad but high-intent service discovery; service hub is cleaner than the homepage.
- Keyword reality: 12 enabled / 12 paused / 9 enabled keywords with impressions in the last 30d
- Top keyword evidence:
  - `home care agency near me` (EXACT, ENABLED) — 148 impr / 19 clicks / $141.73 / 0.0 conv
  - `home care agency near me` (PHRASE, ENABLED) — 138 impr / 8 clicks / $49.90 / 0.0 conv
  - `private caregiver near me` (EXACT, ENABLED) — 75 impr / 13 clicks / $88.67 / 0.0 conv
  - `private caregivers near me` (EXACT, ENABLED) — 32 impr / 13 clicks / $64.27 / 0.0 conv
  - `caregiver near me` (EXACT, PAUSED) — 29 impr / 7 clicks / $42.76 / 0.0 conv
  - `home care near me` (EXACT, PAUSED) — 28 impr / 2 clicks / $26.48 / 0.0 conv
  - `private home care for elderly near me` (EXACT, ENABLED) — 27 impr / 0 clicks / $0.00 / 0.0 conv
  - `private sitters for elderly near me` (EXACT, ENABLED) — 25 impr / 2 clicks / $15.91 / 0.0 conv
- Locked live comparators:
  - RSA `799582490639` — `ENABLED` — `EXCELLENT` — homepage URL — 330 impr / 48 clicks / 14.55% CTR / $334.21 spend / 0.0 conv
    - Headlines:
      - Private Home Care Near Me
      - FirstLight Home Care
      - Non-Medical Home Care
      - Local Boston NW Team
      - No Weekly Minimums
      - Talk To A Care Advisor
      - Private Caregiver Near You
      - Licensed & Insured
      - Get Care This Week
      - Home Care Agency Near Me
      - Trusted Local Caregivers
      - Private Duty Home Care
      - Serving Boston NW Families
      - Care For Aging Parents
      - Call For A Free Consult
    - Descriptions:
      - Private-pay in-home care from a local team. Speak with a care coordinator today.
      - Non-medical home care with no weekly minimums. Call to discuss the right fit.
      - Trusted caregivers for seniors across Boston Northwest. Get clear next steps fast.
      - Need care soon? Talk with FirstLight about private home care that starts simply.
  - RSA `797739750179` — `PAUSED` — `GOOD` — homepage URL — 181 impr / 20 clicks / 11.05% CTR / $102.41 spend / 0.0 conv
    - Headlines:
      - Home Care Near You
      - Local Caregivers You Trust
      - Compassionate Care Nearby
      - Your Neighbors Trust Us
      - Serving Boston NW Families
      - Care When You Need It
      - FirstLight Home Care
      - No Weekly Minimums
      - Flexible Home Support
      - Private Caregiver Options
      - Care That Fits Your Family
      - Trusted Local Agency
      - Free Consultation Today
      - Talk To A Care Advisor
      - Start Care This Week
    - Descriptions:
      - Compassionate home care from people who understand. Serving Arlington, Cambridge & more.
      - Your loved one deserves care that feels like family. No minimums - start with what works.
      - Local caregivers who treat your family like their own. Free consultation - call today.
      - We've been in your shoes. Let us help your family find the right care solution.
  - RSA `802660468722` — `ENABLED` — `PENDING` — service-hub URL — 0 impr / 0 clicks / 0.00% CTR / $0.00 spend / 0.0 conv
    - Headlines:
      - Private Home Care Near Me
      - Home Care Services Near You
      - Private Duty Home Care
      - FirstLight Home Care
      - Local Boston NW Team
      - No Weekly Minimums
      - Talk To A Care Advisor
      - Get Care This Week
      - Trusted Local Caregivers
      - Licensed & Insured
      - Care For Aging Parents
      - Flexible In-Home Support
      - Home Care Agency Near Me
      - Private Pay Care At Home
      - Free Consultation Today
    - Descriptions:
      - Private-pay home care from a local Boston NW team.
      - See companion, personal, respite, dementia, and live-in care.
      - No weekly minimums and flexible in-home support.
      - Need care soon? Get clear next steps from a care advisor.

### Locked Notes

- Only the `### Editable Challenger` block below may change.
- Keep the fixed recommended URL on the service hub.
- Judge this challenger primarily against live winner `799582490639`, with `797739750179` as supporting reference.
- Preserve near-me and private-pay intent without drifting into low-quality broad messaging.

### Editable Challenger
Hypothesis: A service-hub challenger that keeps the strongest near-me and private-pay intent terms while making service discovery explicit should protect CTR and send cleaner traffic than the homepage incumbent.
Target query themes:
- home care agency near me
- private caregiver near me
- private home care near me
- private sitters for elderly near me
Fixed recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
Headlines:
- Private Home Care Near Me
- Home Care Services Near You
- Private Duty Home Care
- FirstLight Home Care
- Local Boston NW Team
- No Weekly Minimums
- Talk To A Care Advisor
- Get Care This Week
- Trusted Local Caregivers
- Licensed & Insured
- Care For Aging Parents
- Flexible In-Home Support
- Home Care Agency Near Me
- Private Pay Care At Home
- Free Consultation Today
Descriptions:
- Private-pay home care from a local Boston NW team.
- See companion, personal, respite, dementia, and live-in care.
- No weekly minimums and flexible in-home support.
- Need care soon? Get clear next steps from a care advisor.
Why this should beat current live ads:
- It retains the exact near-me and private-pay language already proving attractive in the live account.
- The service-hub destination should better satisfy broad service-discovery clicks than the homepage.
- The copy keeps urgency and trust while making the available service set more explicit before the click.

4. Locked Reference Ad Groups

## Caregiver Services

- Ad Group ID: `192086084094`
- Status: `PAUSED`
- Role in campaign: **LEGACY PAUSED**
- Purpose: Older generic caregiver demand bucket from pre-reset structure; now mostly a comparison artifact / cleanup target.
- Recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- Top keyword evidence:
  - `caregiver services` (PHRASE, ENABLED) — 114 impr / 6 clicks / $13.60 / 0.0 conv
  - `home caregiver` (PHRASE, ENABLED) — 58 impr / 6 clicks / $13.45 / 0.0 conv
  - `professional caregiver` (PHRASE, ENABLED) — 39 impr / 5 clicks / $12.41 / 0.0 conv
- Incumbent winner: `797661377482` — 123 impr / 10 clicks / 8.13% CTR / $25.78 / 0.0 conv / service-hub URL

## City-Specific

- Ad Group ID: `193039051803`
- Status: `PAUSED`
- Role in campaign: **LEGACY PAUSED**
- Purpose: Older city-modified structure from pre-reset setup; city learning should now stay inside the core campaign, not a separate active branch.
- Recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- Top keyword evidence:
  - `home care boston ma` (PHRASE, ENABLED) — 52 impr / 7 clicks / $14.05 / 0.0 conv
  - `elderly care boston ma` (PHRASE, ENABLED) — 22 impr / 0 clicks / $0.00 / 0.0 conv
  - `senior care boston ma` (PHRASE, ENABLED) — 16 impr / 0 clicks / $0.00 / 0.0 conv
- Incumbent winner: `797718501022` — 83 impr / 5 clicks / 6.02% CTR / $9.99 / 0.0 conv / homepage URL

## Companion / Private Caregiver

- Ad Group ID: `193039051643`
- Status: `PAUSED`
- Role in campaign: **PAUSED CLEANUP SHELL**
- Purpose: Hold companion/private-caregiver adjacency themes on a short leash when query quality justifies it.
- Recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/companion-care/`
- Top keyword evidence:
  - `caregiver services` (PHRASE, PAUSED) — 134 impr / 11 clicks / $55.77 / 0.0 conv
  - `private caregiver` (PHRASE, PAUSED) — 26 impr / 3 clicks / $18.44 / 0.0 conv
  - `companion care services` (PHRASE, PAUSED) — 17 impr / 2 clicks / $11.20 / 0.0 conv
- Incumbent winner: `799582490762` — 119 impr / 11 clicks / 9.24% CTR / $57.10 / 0.0 conv / companion-care URL

## Problem-Aware Parents

- Ad Group ID: `194857141833`
- Status: `PAUSED`
- Role in campaign: **LEGACY PAUSED**
- Purpose: Top-of-funnel/problem-aware adult-child intent. Kept paused during reset because it tends to dilute commercial focus.
- Recommended URL: `https://www.firstlighthomecare.com/home-healthcare-boston-northwest/home-care-services/`
- Top keyword evidence:
  - `senior care options` (PHRASE, ENABLED) — 31 impr / 3 clicks / $2.48 / 0.0 conv
  - `care for elderly parents` (PHRASE, ENABLED) — 30 impr / 0 clicks / $0.00 / 0.0 conv
  - `elder care options` (PHRASE, ENABLED) — 16 impr / 0 clicks / $0.00 / 0.0 conv
- Incumbent winner: `797739735353` — 45 impr / 3 clicks / 6.67% CTR / $2.48 / 0.0 conv / homepage URL
