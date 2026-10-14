# MVP Builder, Fractional leadership and Dev Leads

How CloudWAV's MVP Builder, the Fractional offering, Dev Leads and the Lead partner sponsorship work in PartnerWAV.
Code: `partnerwav-v11-merged.html` (search for "Fractional leadership, the MVP Builder wizard and Dev Leads").
Database rules: `supabase/portal_records.sql` (`projectReferrals`, `serviceRequests`, `productStages`).

## Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | How long a software house has | **5 business days** to accept or decline a lead, **10 business days** to send a quote after accepting, and the lead is **closed or moved on within 30 days** of being sent. PartnerWAV tracks each step. |
| 2 | Who holds the client | **The current referral model.** The software house contracts with the client and pays PartnerWAV the referral fee under the Software Project Referral Agreement. PartnerWAV never becomes the contract holder, so no new delivery-partner agreement is needed. |
| 3 | Which fractional roles | **All four** from the SaaS Growth Partner Agreement: CTO, CAIO, CIO and CISO. |
| 4 | Partners, vendors and affiliates without a dev team | **The wizard decides.** Everyone can reach the MVP Builder through the wizard, and a leadership need goes to Fractional. Nobody is turned away. |
| 5 | When Fractional appears | **Once the product is built and live.** It opens when the company says its product is live or raising and scaling, or when one of its MVP builds is marked delivered. |

## The MVP Builder wizard

"Find the right help" on the MVP Builder page asks five things:

1. **Where the product is today**: idea, building the first version, live with first users, or raising and scaling.
2. **Who builds it today**: in-house developers, an agency or freelancers, or no developers yet.
3. **What they need** (any number): a first version or prototype, a full app, a fix or finished feature, a security review, investor-ready features, extra developers, or leadership (then which fractional roles).
4. **Budget and details**: budget, timing, what it's for and an optional link.
5. **Suggestion**: the wizard shows where each part goes, then sends it.

The product stage is saved for the company, and is editable on the MVP Builder page.

### Routing

| What they asked for | Goes to |
|---------------------|---------|
| A full app or investor-ready build **and** a budget of USD 5,000 or more | A software house as a **Dev Lead** (Full MVP or Investor-ready package) |
| Anything else that is a build, fix, review or extra developers | CloudWAV's MVP Builder package (Quick MVP, Quick fix, Secure code review, Investor-ready, Extra developers, Full MVP) |
| Leadership (any roles) | A **Fractional** request, always, sent with the build if there is one |

The rules are in `mvpRoute()`. The biggest build need decides the package. A small or unknown budget keeps a full app with CloudWAV, and CloudWAV can move it to a house once it has been quoted.

## Fractional leadership

- A page with the four roles and a request form (roles, start, time needed, what is going on).
- Opens in the menu once the company's product is live (see decision 5). Before then it shows a note and the form still works, so no request is lost.
- Requests are `serviceRequests` with `kind: "fractional"`, handled in Services & Sponsors like the other requests.
- Vendor assessment: the **Fractional leadership** add-on replaces the MVP Builder add-on. Choosing it asks which roles would help most. The old MVP Builder add-on stays in the price list as `legacy` so older assessments still read correctly, but is hidden from the wizard and quote editor.

## Dev Leads

A Dev Lead is a **project referral** (the same record as a software referral, with `source: "mvp"`). It is created when CloudWAV sends an MVP request to a software house in Services & Sponsors, so the referral is registered with the house and tracked from that moment.

- Timeline: `respondBy` (5 business days), `quoteBy` (10 business days after accepting), `closeBy` (30 days after it was sent). The page shows the next date, and an overdue lead is flagged.
- Stages the house records: **Accept** or **Decline**, **Quote sent** (with an amount), **Won: contract signed** (with an amount), **Lost**, **Delivered**. Any step can have a progress note. Each step is logged with its date.
- **Delivered** marks the MVP request as built and live, which opens Fractional for that company.
- **Move on** (CloudWAV): an overdue or declined lead moves to another house. The old lead is kept with status "Moved to another house", and the new one records where it came from.
- A house's own login sees its Dev Leads under **Dev Leads** in its menu. A software house is a company whose house record is linked to that login (Software houses, "Their partner account on PartnerWAV" or the vendor program).
- The house can't change the client, the dates, who sent the lead, or move it to another house. It can only move a lead forward: registered to accepted or declined, accepted to quoted or lost, quoted to won or lost.

### Open point: the referral agreement

Clause 3 of the Software Project Referral Agreement says a referral not rejected in time is **deemed accepted**. The 5-day move-on for Dev Leads (decision 1) conflicts with that: an unanswered Dev Lead shows as overdue and can be moved on, but a lead the house is deemed to hold may be protected. Before Dev Leads go live, decide one of:

- change clause 3 so that MVP-sourced leads move on after 5 business days (and say so to houses), or
- keep the deemed-acceptance rule and only move a lead on before day 5.

Until that's decided, the app treats Dev Leads as **not** deemed accepted (`refStatus()` skips the rule for `source: "mvp"`).

## Lead partner (sponsorship)

A software house can be a **Lead partner** in Services & Sponsors. It gets **first look** at Dev Leads: in the house choice, Lead partners are listed first and marked "(Lead partner)", and the house's listing shows the badge. A specialty and a monthly fee (USD) are recorded for it. CloudWAV sets it; a house can't set it for itself.

Interpretation: the brief named the sponsorship without defining it. This is the reading used here. Change `houseOptions()` and the Lead partner tab if the intended benefit is different.

## Where things are

| Place | What's there |
|-------|--------------|
| MVP Builder page | Find the right help (wizard), product stage, packages, Fractional prompt once live |
| Fractional Leadership (menu, once live) | Roles, request form, the company's Fractional requests |
| Dev Leads (menu, software houses) | The house's leads: accept, quote, won, delivered, notes |
| CloudWAV → Services & Sponsors | MVP Builder requests (assign a house), Fractional requests, Dev leads (open, overdue, move on), Lead partners, Sponsorships, Promoters, Packages |
| Vendor wizard, add-ons | Fractional leadership (asks which roles) |

## Data and privacy

- Local state: `partnerWAV_mediaMvp` (requests, `stages`), `partnerWAV_softwareReferrals` (dev leads as `projectReferrals`, houses with `leadPartner`).
- Cloud sync (`cloudSchedule`): `serviceRequests` (requester, CloudWAV), `productStages` (each company only), `projectReferrals` (referrer, CloudWAV, and the house's own login only for `source: "mvp"`).
- SQL: `serviceRequests` accepts `kind: "fractional"`. A software house may move its own `source: "mvp"` leads through the stages above. Nobody else may set `source`, so a referrer can't create a Dev Lead. Covered by `tests/sql/test_portal_records.sql`.

## Tests

- `tests/test_media_mvp.py`: the vendor wizard offers Fractional leadership, not the MVP Builder.
- `tests/test_fractional_devlead.py`: wizard routing, Fractional unlock, Dev Lead from assignment to delivered, Lead partner, house login.
- `tests/test_nav_sections.py`: menu link counts (Fractional and Dev Leads are added, hidden until they apply).
- `tests/sql/test_portal_records.sql`: the house and referrer rules above, plus Fractional requests and product-stage privacy.

## Open items

1. **Referral agreement (clause 3)**: see the open point above. This is a decision for CloudWAV, not for code.
2. **Days**: quote and response are business days, and the 30-day close is calendar days. Confirm with the user.
3. **Move on is manual**: overdue leads are flagged, but CloudWAV moves them on. Automatic moves on day 5 would need the clause 3 decision first.
4. **Deploy the SQL**: run `supabase/portal_records.sql` on the project before houses use Dev Leads. Without it, the house's updates are refused.
