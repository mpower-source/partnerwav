#!/usr/bin/env python3
"""Source of truth for the full text of CloudWAV's four PartnerWAV agreements.

The text was written out from the agreement outlines in the PartnerWAV project (docs 01-04) and the
planning brief, and follows their section numbering (e.g. Vendor Program 5.2 CloudWAV's compensation, 5.4 Net
Revenue, 6.3-6.5 non-circumvention, 13.2/13.5 symmetric termination; Joint Venture 3, 5-6, 7, 8, 10, 12, 14;
Custom Marketing 1.3, 4, 6; Reseller 2, 5, 6).

  python3 tools/agreement_templates.py js    -> prints the AGR_TEMPLATE_TEXT block for partnerwav-v11-merged.html
  python3 tools/agreement_templates.py json  -> prints JSON for tools/build_agreement_docx.js

{{name}} is filled by the portal; "fields" are what CloudWAV completes on each agreement ("def" = standard value).
"""
import json, sys
NOTE = "DRAFT -- not for execution until both parties and their counsel have reviewed it. Highlighted text was filled in by PartnerWAV for this agreement."
COMMON_FIELDS = {
  "effectiveDate": {"label": "Effective date", "type": "date"},
  "cloudwavEntity": {"label": "CloudWAV legal entity, registration no. and address"},
  "partyEntity": {"label": "Their legal entity, registration no. and address"},
  "governingLaw": {"label": "Governing law (e.g. the laws of the State of Wyoming, USA)"},
  "arbitrationSeat": {"label": "Seat and rules of arbitration"},
  "cloudwavContact": {"label": "CloudWAV contact for notices"},
  "partyContact": {"label": "Their contact for notices (name, email)"},
}
def F(extra): d = dict(COMMON_FIELDS); d.update(extra); return d
DISPUTES = [
  "The parties will first try to resolve any dispute through their named business contacts within 15 business days of written notice of the dispute.",
  "If that fails, the dispute goes to mediation with a neutral mediator, the cost shared equally.",
  "If mediation does not resolve the dispute within 45 days, it is finally settled by binding arbitration, not litigation: {{arbitrationSeat}}. The arbitration is conducted in English. Each party bears its own legal costs unless the arbitrator finds a party acted in bad faith.",
  "This Agreement is governed by {{governingLaw}}.",
  "Nothing in this clause stops a party from seeking urgent interim relief from a court to protect its confidential information or intellectual property."
]
GENERAL = [
  "Notices under this Agreement are sent in writing to: CloudWAV -- {{cloudwavContact}}; {{partyName}} -- {{partyContact}}. A party may change its contact by written notice.",
  "This Agreement, with its Schedules, is the whole agreement between the parties on its subject and replaces earlier discussions and drafts. It can be changed only in writing signed by both parties; the Schedules can be updated through the PartnerWAV portal where this Agreement says so.",
  "Neither party may assign this Agreement without the other's written consent, which will not be unreasonably withheld, except to a successor to all or substantially all of its business.",
  "The parties are independent contractors. Nothing in this Agreement creates an employment, agency or franchise relationship, and neither party may bind the other.",
  "If a provision is found unenforceable, the rest of the Agreement stays in force. A failure to enforce a right is not a waiver of it.",
  "Neither party is liable for delay or failure caused by events beyond its reasonable control, for as long as the event lasts.",
  "This Agreement may be signed electronically and in counterparts."
]
T = {}

# ================================================================== 1. Vendor Program Agreement
T["Vendor Program Agreement"] = {
 "title": "PartnerWAV Vendor Program Agreement",
 "file": "PartnerWAV_Vendor_Program_Agreement",
 "summary": "The master agreement a vendor signs to run its Program on PartnerWAV, with CloudWAV as Program Operator.",
 "note": NOTE,
 "parties": [
  "This Vendor Program Agreement (the \"Agreement\") is made on {{effectiveDate}} between:",
  "(1) {{cloudwavEntity}} (\"CloudWAV\" or the \"Program Operator\"); and",
  "(2) {{partyEntity}} (\"{{partyName}}\" or the \"Vendor\").",
  "CloudWAV operates the PartnerWAV platform, through which vendors run partner programs and resellers, affiliates, channel managers and certified installers sell and deliver vendors' products. The Vendor wishes to run its program, {{programName}}, on PartnerWAV with CloudWAV as Program Operator. The parties agree as follows."
 ],
 "sections": [
  {"title": "Appointment and Program scope", "clauses": [
    "The Vendor appoints CloudWAV as Program Operator of the {{programName}} program (the \"Program\") on PartnerWAV, covering the products and services described in Schedule A (the \"Products\").",
    "The Program operates in the territory stated in Schedule D (the \"Territory\"). The appointment is {{exclusivity}} in the Territory.",
    "As Program Operator, CloudWAV recruits, enrolls, enables and manages Partners for the Program, operates deal registration and commission tracking, and manages the Certified Installer Network where Schedule C applies.",
    "The Vendor remains responsible for the Products, their pricing, their terms of sale to customers, and customer support, unless a Schedule says otherwise.",
    "\"Partner\" means a reseller, affiliate, referral partner, channel manager or certified installer enrolled in the Program through PartnerWAV. \"Customer\" means an end customer that buys the Products through or as a result of a Partner or CloudWAV. \"Commission\", \"Override\" and \"Net Revenue\" have the meanings in clauses 4 and 5."
  ]},
  {"title": "The tier ladder", "clauses": [
    "Affiliate / Referral: the lightest tier. The Partner refers a customer and is paid a flat or percentage payout per referral, with no negotiated contract.",
    "Reseller: the Partner registers deals and earns Commission on the agreed base for the agreed duration.",
    "Channel Manager / Master Agent: the Partner recruits and manages sub-resellers and earns an Override in addition to the base rate, never carved out of it."
  ]},
  {"title": "Tier availability and enrollment", "clauses": [
    "The tiers the Vendor makes available for this Program, and the rate and base for each, are set out in Schedule B.",
    "The Vendor may open or close a tier for new enrollments on 30 days' notice. Partners already enrolled keep their tier and rates for deals registered before the change.",
    "Partners join the Program under CloudWAV's master Reseller Agreement, which incorporates the rates in Schedule B by reference. The Vendor will not require a Partner to sign separate terms that conflict with this Agreement."
  ]},
  {"title": "Commission", "clauses": [
    "The Vendor pays Commission on every sale of the Products to a Customer that is attributable to a Partner or to CloudWAV, at the rates in Schedule B.",
    "Commission is calculated on {{revenueBaseText}}, as defined in clause 5.4.",
    "Commission on renewals and recurring revenue continues for {{renewalDuration}} from the Customer's first purchase, at the renewal rate in Schedule B.",
    "Discounts the Vendor chooses to give a Customer reduce the revenue on which Commission is calculated only to the extent they reduce what the Customer actually pays; they are not otherwise deducted."
  ]},
  {"title": "Override, installer margin, CloudWAV's compensation and Net Revenue", "clauses": [
    "A Channel Manager earns the Override in Schedule B on sales made by the sub-resellers it recruited. CloudWAV acts as Channel Manager for the Partners it recruits into the Program and earns the Override on their sales.",
    "The Override is additive: it is paid on top of the sub-reseller's Commission as a separate line and is never taken out of it. CloudWAV's compensation for operating the Program is the Override, the platform operator fee and, where Schedule C applies, the Installer Network margin. {{platformFeeText}} The Vendor also pays the monthly PartnerWAV subscription stated in Schedule B for its use of the platform. No other platform, listing or set-up fee is payable unless the parties agree it in writing.",
    "{{installerMarginText}}",
    "\"Net Revenue\" means the amounts actually invoiced to and collected from the Customer for the Products, less only these deductions: {{deductionsText}}. Every deduction must be itemized line by line on the commission statement, supported by documents the Vendor provides on request, and of a kind approved in advance in Schedule B. No deduction that is not listed there may be taken without CloudWAV's prior written agreement.",
    "The Vendor issues a statement for each payout period showing, for each Customer, the invoices issued, amounts collected, deductions taken, the Commission and Override due and the Partner credited.",
    "Payment is made {{payoutSchedule}}, in {{currency}}, with a minimum payout of {{minPayout}} {{currency}}; smaller amounts carry over to the next period.",
    "CloudWAV may, once a year on 30 days' notice, have an independent accountant review the Vendor's records for the Program. If the review shows an underpayment of more than 5%, the Vendor pays the shortfall and the reasonable cost of the review.",
    "Each party is responsible for its own taxes. Where the law requires tax to be withheld from a payment, the payer withholds it, pays it to the authority on time and gives the payee the certificate."
  ]},
  {"title": "Deal registration and conflict rules", "clauses": [
    "Partners register deals through PartnerWAV. The Vendor will approve or challenge a registration within {{approvalSlaDays}} business days; a registration not challenged in that time is treated as approved. The Vendor may challenge only where the customer is an existing customer of the Vendor for the same Product, or is in documented active discussions with the Vendor or with another Partner that registered first, and must share reasonable evidence.",
    "An approved registration is protected for {{dealProtectionDays}} days. If the Customer buys within that period, the registering Partner earns the Commission whichever channel takes the order. Protection extends while there is documented active engagement with the Customer.",
    "{{nonCircumventionText}}",
    "If the Vendor breaches clause 6.3, the Commission, Override and other amounts that would have been due on the deal remain payable as if it had closed through the registering Partner.",
    "Where two Partners claim the same Customer, the earlier approved registration prevails. CloudWAV decides conflicts between Partners after hearing both, and the Vendor will follow that decision for Commission purposes."
  ]},
  {"title": "Certified Installer Network", "clauses": [
    "Model A -- on-site installation. Where the Products include hardware that needs installation at the Customer's site, installation jobs are posted, claimed, delivered and signed off through PartnerWAV by installers certified under Schedule C. The installer is paid the flat fee or day rate stated for the job, and CloudWAV earns the Installer Network margin on installer billings.",
    "Model B -- direct-to-user fulfillment. Where hardware ships straight to the Customer with no installation, no installer is involved and Commission runs through the Reseller or Affiliate line in Schedule B.",
    "Certification requirements, countries covered, job types and the payout and reconciliation cycle for installers are set out in Schedule C. If Schedule C is marked not applicable, this clause does not apply to the Program."
  ]},
  {"title": "Vendor Resource Library and marketing materials license", "clauses": [
    "The Vendor will provide and keep current the training, product and marketing materials Partners reasonably need to sell the Products, including recorded webinars, collateral and case studies, and upload them to the Vendor Resource Library on PartnerWAV so that Partners can use them on demand.",
    "The Vendor grants CloudWAV and enrolled Partners a non-exclusive, royalty-free license for the term of this Agreement to use, reproduce and display those materials and the Vendor's names and logos for customer-facing and internal sales enablement, with the attribution and brand guidelines the Vendor provides.",
    "CloudWAV reviews uploads before they are published to check they are marketing or training content and not internal or confidential documents. The review standard and turnaround are in Schedule E."
  ]},
  {"title": "Professional services", "clauses": [
    "{{proServicesText}}",
    "Fees for professional services belong to whoever delivers them and are not Net Revenue, unless the Vendor itself invoices them as part of a Product sale."
  ]},
  {"title": "Data, confidentiality and feedback", "clauses": [
    "Each party will keep the other's confidential information confidential, use it only for this Agreement, and protect it with reasonable care. This does not apply to information that is public, already known, independently developed or lawfully received from someone else, or that must be disclosed by law.",
    "Partner contact data, deal registration history and performance data generated on PartnerWAV are held by CloudWAV. The Vendor may use the data relating to its own Program to run and improve the Program and to serve Customers, and for no other purpose.",
    "Each party will comply with the data protection laws that apply to it, including the GDPR, Thailand's PDPA and US state privacy laws where relevant, and will tell the other without undue delay of any data breach affecting the other's data.",
    "The Vendor will consider in good faith product feedback and feature requests passed on by CloudWAV and Partners. Feedback may be used freely by the Vendor without payment.",
    "Confidentiality obligations continue for 3 years after this Agreement ends. On request after termination each party returns or deletes the other's confidential information, except what it must keep by law."
  ]},
  {"title": "Intellectual property", "clauses": [
    "The Vendor keeps all rights in the Products, their documentation and its training and marketing materials. CloudWAV keeps all rights in PartnerWAV, its processes, content and data model. Partners keep the rights in their own marketing and their customer data.",
    "No license is granted beyond what is needed to market, sell and support the Products and to use the Resource Library under this Agreement.",
    "The Vendor warrants that it has the right to sell the Products and license the materials in the Territory, and that their marketing and sale as contemplated here do not infringe third-party rights."
  ]},
  {"title": "Compliance", "clauses": [
    "Each party is responsible for complying with the laws that apply to its own business in its own jurisdictions, including anti-bribery, export control and sanctions laws.",
    "Each party confirms that neither it nor its owners or directors are on any applicable sanctions list, including the OFAC SDN list.",
    "The Vendor warrants that the Products are lawful to resell in the Territory and will hold the approvals and maintain the insurance set out in Schedule F."
  ]},
  {"title": "Term and termination", "clauses": [
    "This Agreement starts on the Effective Date and runs for an initial term of {{termMonths}} months. {{renewalText}}",
    "Either party may terminate for convenience on {{terminationNoticeDays}} days' written notice. The notice period is the same for both parties.",
    "Either party may terminate immediately by written notice if the other commits a material breach and does not cure it within {{cureDays}} days of written notice, or becomes insolvent.",
    "After termination: (a) deals registered before the termination date remain protected and commissionable until they close or their protection ends; (b) Commission and Override on Customers won before termination continue to be paid for {{commissionTailMonths}} months; (c) the parties cooperate on an orderly wind-down and a joint communication to Partners.",
    "Any post-termination restriction on either party is proportionate: it is limited to {{postTerminationMonths}} months and to not soliciting the other's Partners or Customers introduced under the Program. No broader non-compete applies to either party."
  ]},
  {"title": "Liability, indemnification and dispute resolution", "clauses": [
    "Each party indemnifies the other against third-party claims arising from its infringement of intellectual property rights, its breach of confidentiality or data protection obligations, or its negligence or wilful misconduct.",
    "Neither party is liable for indirect or consequential loss or loss of profit. Each party's total liability under this Agreement is limited to {{liabilityCap}}. These limits do not apply to the indemnities above, to unpaid Commission, Override or fees, or to liability that cannot be limited by law."
  ] + DISPUTES},
  {"title": "General", "clauses": GENERAL}
 ],
 "schedules": [
  {"title": "Schedule A -- Program details", "rows": [
    ["Vendor", "{{partyName}}"], ["Program", "{{programName}}"], ["Vertical", "{{vertical}}"],
    ["Products", "{{productsText}}"], ["Relationship type", "{{relationshipsText}}"], ["Launch date", "{{effectiveDate}}"]]},
  {"title": "Schedule B -- Commission and Override economics", "rows": [
    ["Tiers, rates and bases", "{{tiersTable}}"], ["Revenue base", "{{revenueBaseText}}"], ["Permitted deductions", "{{deductionsText}}"],
    ["Renewal / recurring duration", "{{renewalDuration}}"], ["Payout schedule", "{{payoutSchedule}}"], ["Currency and minimum payout", "{{currency}}; minimum {{minPayout}} {{currency}}"],
    ["Platform operator fee", "{{platformFeeShort}}"], ["PartnerWAV subscription", "{{planFee}}"], ["Deal protection", "{{dealProtectionDays}} days from approval; approval within {{approvalSlaDays}} business days"]]},
  {"title": "Schedule C -- Installer Network", "rows": [
    ["Installer Network", "{{installerScheduleText}}"], ["Certification, countries and job types", "{{installerDetails}}"]]},
  {"title": "Schedule D -- Territory and exclusivity", "rows": [
    ["Territory", "{{territory}}"], ["Exclusivity", "{{exclusivity}}"]]},
  {"title": "Schedule E -- Resource Library guidelines", "rows": [
    ["Approved content", "Training recordings, product documentation, marketing collateral, case studies and approved messaging. No internal or confidential documents."],
    ["Review turnaround", "CloudWAV reviews uploads within 3 business days."],
    ["Use", "Customer-facing and internal sales enablement by enrolled Partners, with the Vendor's attribution and brand guidelines."]]},
  {"title": "Schedule F -- Insurance and compliance", "rows": [
    ["Insurance and approvals", "{{insurance}}"], ["Breach notification", "Without undue delay, and in any case within 72 hours of becoming aware."]]}
 ],
 "html": ["tiersTable"],
 "fields": F({
  "territory": {"label": "Territory (countries or regions)"},
  "planFee": {"label": "PartnerWAV plan and monthly fee (e.g. Growth plan, USD 1,497 a month)"},
  "exclusivity": {"label": "Exclusivity", "def": "non-exclusive"},
  "cureDays": {"label": "Cure period (days)", "def": "30"},
  "liabilityCap": {"label": "Liability cap", "def": "the total Commission, Override and fees paid or payable under this Agreement in the 12 months before the claim"},
  "installerDetails": {"label": "Installer certification, countries and job types", "def": "Not applicable unless the parties complete this Schedule"},
  "insurance": {"label": "Insurance and approvals the Vendor maintains", "def": "As required by law for the Products in the Territory, and as the parties agree in writing"}
 }),
 # how the Word template (not tied to one vendor) words the parts the portal fills from a program's settings
 "doc": {
  "programName": "[Program name]", "partyName": "[Vendor name]", "vertical": "[Vertical]", "productsText": "[Products and services covered]", "relationshipsText": "Vendor Program",
  "revenueBaseText": "Net Revenue", "deductionsText": "refunds and chargebacks; sales tax or VAT actually remitted; payment processing fees",
  "renewalDuration": "36 months", "currency": "USD", "payoutSchedule": "every 30 days", "minPayout": "100",
  "dealProtectionDays": "90", "approvalSlaDays": "3", "termMonths": "24", "terminationNoticeDays": "60", "postTerminationMonths": "6", "commissionTailMonths": "12",
  "renewalText": "It then renews automatically for successive 12-month periods unless either party gives notice of non-renewal at least 60 days before the end of the current term.",
  "installerMarginText": "On jobs delivered through the Certified Installer Network, CloudWAV earns the Installer Network margin stated in Schedule C on installer billings, separate from Commission. If Schedule C is marked not applicable, no Installer Network margin applies.",
  "installerScheduleText": "[Applies / Not applicable]. CloudWAV margin on installer billings: [__]%",
  "platformFeeText": "The Vendor pays CloudWAV a platform operator fee of 5% of deal value on sales by Partners CloudWAV brought to the Program and operates for the Vendor, and 2% on sales by Partners the Vendor invited to the Program, invoiced as the Vendor collects from the Customer. The platform operator fee is paid by the Vendor in addition to Commission and never reduces what a Partner earns.",
  "platformFeeShort": "5% (Partners CloudWAV brings and operates); 2% (Partners the Vendor invites); invoiced as the Vendor collects",
  "nonCircumventionText": "The Vendor will not deal directly with a Customer or prospect introduced through a registered deal, or route such a deal through another channel, in order to avoid Commission, Override or other amounts under this Agreement.",
  "proServicesText": "CloudWAV, Partners and certified installers may provide consulting, implementation, integration, training and other professional services to Customers in connection with the Products, on their own terms. The Vendor will not block or restrict this, and may also offer its own services.",
  "tiersTable": [["Tier", "Rate", "Base"], ["Affiliate / Referral", "[__]", "[__]"], ["Reseller", "[__]% first year + [__]% renewal", "Net Revenue"], ["Channel Manager", "Reseller rate + [__]% Override", "Sub-reseller revenue"]]
 }
}

# ================================================================== 2. Joint Venture Agreement
T["Joint Venture Agreement"] = {
 "title": "PartnerWAV Joint Venture Agreement",
 "file": "PartnerWAV_Joint_Venture_Agreement",
 "summary": "For a counterparty entering a new market where CloudWAV brings local channel access, sharing ownership, governance and results.",
 "note": NOTE,
 "parties": [
  "This Joint Venture Agreement (the \"Agreement\") is made on {{effectiveDate}} between:",
  "(1) {{cloudwavEntity}} (\"CloudWAV\"); and",
  "(2) {{partyEntity}} (\"{{partyName}}\").",
  "{{partyName}} wishes to build a business in the Territory, and CloudWAV brings local channel access, market presence and operating expertise there. Rather than a vendor program that pays commission on sales through an existing platform, the parties wish to share ownership, governance and results in a new joint enterprise (the \"Venture\"). The parties agree as follows."
 ],
 "sections": [
  {"title": "Purpose and scope", "clauses": [
    "The purpose of the Venture is: {{purpose}} (the \"Purpose\").",
    "The Venture operates in {{territory}} (the \"Territory\").",
    "The Venture's business model, first products, target customers and go-to-market plan are described in Schedule A. Each party will act in good faith to advance the Purpose."
  ]},
  {"title": "Definitions", "clauses": [
    "\"Ownership Percentages\" means the parties' interests in the Venture under clause 6. \"Reserved Matters\" means the decisions in clause 7.3. \"Background IP\" and \"Venture IP\" have the meanings in clause 10.",
    "\"Business Plan\" means the plan and budget for the Venture approved by both parties from time to time, the first of which is summarized in Schedule B."
  ]},
  {"title": "Structure: entity or contractual", "clauses": [
    "The Venture is structured as: {{structure}}.",
    "Contractual joint venture (the default). No separate legal entity is formed. Each party carries on its part of the Venture through its own company, keeps its own books for it, and is responsible for its own staff and obligations, while the parties share governance under clause 7 and results under clause 8.",
    "Entity joint venture. The parties may instead, or later, agree in writing to form a jointly owned legal entity. This suits a Venture where either party needs clean legal separation from its other business. If they do, they will sign the constitutional and shareholder documents needed to carry these terms across, and this Agreement continues to apply to the extent it is consistent with them."
  ]},
  {"title": "Operations and staffing", "clauses": [
    "Each party provides the people and resources described in Schedule A. People remain employed or engaged by the party that provides them.",
    "Neither party will solicit for employment the other's staff working on the Venture during the term and for 12 months afterwards, without the other's consent. General recruitment advertising is not solicitation."
  ]},
  {"title": "Contributions", "clauses": [
    "CloudWAV contributes: {{cloudwavContribution}}.",
    "{{partyName}} contributes: {{partyContribution}}.",
    "Contributions may be cash, intellectual property, personnel or market access. The agreed value of each contribution and any vesting conditions are recorded in Schedule D.",
    "Neither party is required to contribute further capital. If the Business Plan needs more capital, the parties may contribute in proportion to their Ownership Percentages; if one party does not take up its share, the other may contribute it, and the Ownership Percentages are adjusted on the basis in Schedule D unless the parties agree otherwise."
  ]},
  {"title": "Ownership Percentages", "clauses": [
    "The Ownership Percentages are: CloudWAV {{cloudwavShare}}% and {{partyName}} {{partyShare}}%.",
    "The Ownership Percentages apply to the sharing of profit and loss, to Venture IP, and to the value of the Venture on exit, unless this Agreement says otherwise.",
    "The Ownership Percentages may be agreed independently of the value of the contributions, and change only as this Agreement provides or the parties agree in writing."
  ]},
  {"title": "Governance and Reserved Matters", "clauses": [
    "Delegated decisions. Day-to-day decisions within the Business Plan are delegated to the operating committee, which has an equal number of representatives from each party and meets at least monthly. Delegated decisions include hiring within budget, marketing spend within budget and approval of individual deals.",
    "The parties' senior representatives meet at least quarterly to review performance against the Business Plan.",
    "Reserved Matters. The following need the unanimous written consent of the parties: (a) the annual budget and Business Plan; (b) new product launches or major feature additions; (c) changes to go-to-market strategy, pricing or territories; (d) raising external capital or taking on material debt; (e) licensing intellectual property to third parties; (f) terminating or materially amending a major contract; (g) changes to ownership or governance; (h) transactions with a party's related parties. The full matrix is in Schedule C.",
    "Deadlock. If the parties cannot agree on a Reserved Matter within 30 days, it is escalated to their chief executives, then to mediation. If it remains unresolved 60 days after mediation starts, either party may start the exit process in clause 14."
  ]},
  {"title": "Profit and loss allocation", "clauses": [
    "Revenue of the Venture is: {{revenueSplit}}.",
    "Expenses in the approved budget are shared in the Ownership Percentages, unless the budget attributes a cost to one party. Each party bears its own costs outside the budget.",
    "Net profit is distributed {{distributionSchedule}}. Reinvestment: {{reinvestment}}.",
    "Each party is responsible for its own taxes on its share."
  ]},
  {"title": "Accounts and reporting", "clauses": [
    "Each party keeps accurate records of Venture revenue and costs and gives the other access to them on reasonable notice.",
    "The parties prepare a joint statement of Venture revenue, costs and net profit each quarter, and reconcile it against the Business Plan."
  ]},
  {"title": "Intellectual property: Background IP and Venture IP", "clauses": [
    "\"Background IP\" is the intellectual property each party owned or developed before this Agreement or independently of the Venture. Each party keeps its Background IP, listed in Schedule F.",
    "Each party grants the other a non-exclusive, royalty-free license to use its Background IP only for the Purpose in the Territory and only during the term. Neither party may use the other's Background IP for any other business without written consent.",
    "\"Venture IP\" is intellectual property created by or for the Venture after the Effective Date. Venture IP is owned by the parties in their Ownership Percentages. Either party may use Venture IP outside the Venture only with the other's written consent.",
    "If the Venture ends, Venture IP is dealt with under Schedule E: the continuing party may buy out the other's share at the exit valuation, failing which each party receives a non-exclusive license to use it."
  ]},
  {"title": "Confidentiality", "clauses": [
    "Each party will keep confidential the other's confidential information, including customer lists, pricing, product roadmaps and technology, and use it only for the Venture.",
    "This does not apply to information that is public, already known, independently developed, or required to be disclosed by law.",
    "These obligations continue for {{confidentialityYears}} years after this Agreement ends. A breach entitles the other party to seek an injunction as well as damages."
  ]},
  {"title": "Non-compete: Territory and Purpose only", "clauses": [
    "During the term, neither party will, without the other's written consent, carry on in the Territory a business that competes with the Purpose. For CloudWAV this means operating a program for a directly competing product in the Territory; for {{partyName}} it means launching its own direct sales operation in the Territory that competes with the Venture.",
    "The restriction is limited to the Purpose and the Territory. Each party remains free to carry on its other products, programs and territories.",
    "After termination the restriction continues for {{nonCompeteYears}} years in this form: in the first year the departing party will not actively solicit the Venture's customers, though existing customers may choose to stay with either party; after that no restriction applies.",
    "The agreed remedy for a breach of this clause is liquidated damages of {{liquidatedDamages}}, which the parties accept is a genuine pre-estimate of loss."
  ]},
  {"title": "Term and termination", "clauses": [
    "This Agreement starts on the Effective Date and runs for an initial term of {{termYears}} years. It renews automatically for successive 12-month periods unless either party gives at least {{renewalNoticeDays}} days' notice before the end of the current term.",
    "Either party may terminate for material breach that is not cured within {{cureDays}} days of written notice, or if the other becomes insolvent.",
    "Either party may leave the Venture for convenience on {{renewalNoticeDays}} days' written notice, in which case clause 14 applies.",
    "On termination the parties carry out an orderly wind-down over 90 to 180 days, including a customer transition plan and the handover of intellectual property under Schedule E."
  ]},
  {"title": "Exit, buy-sell and valuation", "clauses": [
    "Trigger events. The exit process starts when: (a) the parties agree to dissolve the Venture; (b) one party wishes to leave and the other to continue; (c) a Reserved Matter remains deadlocked after mediation; or (d) a major market change or force majeure event makes the Purpose impracticable.",
    "Method. The exit method is: {{exitMethod}}. Under an independent valuation, a neutral appraiser the parties agree on (or, failing agreement, one nominated by the arbitration body) values the Venture, and the continuing party may buy the other's interest at its Ownership Percentage of that value. The alternatives in Schedule E (one-bid and shotgun) apply only if the parties choose them there.",
    "The valuation basis is {{valuationBasis}}.",
    "The price is paid in cash on completion unless the parties agree an earn-out, an assumption of liabilities or other terms in writing.",
    "If neither party buys, the parties wind the Venture up, notify customers, hand over intellectual property under Schedule E and share any remaining net assets in their Ownership Percentages."
  ]},
  {"title": "Dispute resolution and governing law", "clauses": DISPUTES},
  {"title": "Liability", "clauses": [
    "Each party is responsible for its own acts and its own staff. Neither party is liable to the other for indirect or consequential loss or loss of profit.",
    "Each party indemnifies the other against third-party claims arising from its breach of this Agreement, its negligence or its infringement of intellectual property rights.",
    "Except for the indemnities, breach of confidentiality and liability that cannot be limited by law, each party's total liability under this Agreement is limited to {{liabilityCap}}."
  ]},
  {"title": "General", "clauses": GENERAL}
 ],
 "schedules": [
  {"title": "Schedule A -- The Venture", "rows": [
    ["Purpose", "{{purpose}}"], ["Territory", "{{territory}}"], ["Business model, first products and target customers", "{{businessModel}}"], ["Structure", "{{structure}}"]]},
  {"title": "Schedule B -- Financial projections", "rows": [
    ["First three years: revenue, margin, operating budget, EBITDA targets and capital needs", "{{financialPlan}}"]]},
  {"title": "Schedule C -- Governance matrix", "rows": [
    ["Delegated to the operating committee", "Hiring, marketing spend and operating costs within the approved budget; approval of individual deals; day-to-day operations."],
    ["Reserved Matters (unanimous)", "Annual budget and Business Plan; new products or major features; go-to-market, pricing or territory changes; external capital or material debt; IP licensing to third parties; major contracts; ownership or governance changes; related-party transactions."],
    ["Meetings", "Operating committee monthly; senior representatives quarterly."],
    ["Deadlock", "Chief executives, then mediation, then the exit process in clause 14."]]},
  {"title": "Schedule D -- Contributions", "rows": [
    ["CloudWAV", "{{cloudwavContribution}}"], ["{{partyName}}", "{{partyContribution}}"],
    ["Ownership Percentages", "CloudWAV {{cloudwavShare}}% / {{partyName}} {{partyShare}}%"], ["Vesting and further contributions", "{{vesting}}"]]},
  {"title": "Schedule E -- Exit mechanics", "rows": [
    ["Method chosen", "{{exitMethod}}"], ["Valuation basis", "{{valuationBasis}}"],
    ["Alternatives available by agreement", "One-bid: one party names a price for the whole Venture and the other chooses to buy or sell at that price. Shotgun: one party offers to buy the other's interest and the other may accept or buy the offeror's interest at 110% of the offered price."],
    ["Venture IP on exit", "Buy-out by the continuing party at the exit valuation; otherwise a non-exclusive license to each party."]]},
  {"title": "Schedule F -- Intellectual property", "rows": [
    ["CloudWAV Background IP", "The PartnerWAV platform, its software, processes, content and data; CloudWAV's partner and channel relationships."],
    ["{{partyName}} Background IP", "{{partyBackgroundIp}}"], ["Venture IP", "Owned in the Ownership Percentages."]]}
 ],
 "html": [],
 "fields": F({
  "purpose": {"label": "Purpose of the Venture"},
  "territory": {"label": "Territory"},
  "businessModel": {"label": "Business model, first products and target customers"},
  "structure": {"label": "Structure", "def": "a contractual joint venture"},
  "cloudwavContribution": {"label": "What CloudWAV contributes"},
  "partyContribution": {"label": "What they contribute"},
  "cloudwavShare": {"label": "CloudWAV %"},
  "partyShare": {"label": "Their %"},
  "vesting": {"label": "Vesting and further contributions", "def": "No vesting. Further contributions adjust the Ownership Percentages at the latest agreed valuation."},
  "revenueSplit": {"label": "How revenue is attributed or split"},
  "distributionSchedule": {"label": "Distribution schedule", "def": "quarterly"},
  "reinvestment": {"label": "Reinvestment policy", "def": "all net profit is reinvested for the first 2 years; after that half is distributed and half retained"},
  "financialPlan": {"label": "Three-year financial plan", "def": "As set out in the Business Plan approved by both parties"},
  "partyBackgroundIp": {"label": "Their Background IP", "def": "Its products, technology, documentation and brands"},
  "confidentialityYears": {"label": "Confidentiality period after termination (years)", "def": "3"},
  "nonCompeteYears": {"label": "Post-termination restriction (years)", "def": "2"},
  "liquidatedDamages": {"label": "Liquidated damages for breach of non-compete"},
  "termYears": {"label": "Initial term (years)", "def": "3"},
  "renewalNoticeDays": {"label": "Notice period (days)", "def": "180"},
  "cureDays": {"label": "Cure period (days)", "def": "60"},
  "exitMethod": {"label": "Exit method", "def": "independent valuation"},
  "valuationBasis": {"label": "Valuation basis", "def": "a multiple of forward EBITDA determined by the appraiser, cross-checked against discounted cash flow"},
  "liabilityCap": {"label": "Liability cap", "def": "the value of that party's contributions to the Venture"}
 }),
 "doc": {"partyName": "[JV Partner name]"}
}

# ================================================================== 3. Custom Marketing Agreement
T["Custom Marketing Agreement"] = {
 "title": "PartnerWAV Custom Marketing Agreement",
 "file": "PartnerWAV_Custom_Marketing_Agreement",
 "summary": "For co-marketing, MDF and event-support commitments without a full Vendor Program.",
 "note": NOTE,
 "parties": [
  "This Custom Marketing Agreement (the \"Agreement\") is made on {{effectiveDate}} between:",
  "(1) {{cloudwavEntity}} (\"CloudWAV\"); and",
  "(2) {{partyEntity}} (\"{{partyName}}\").",
  "The parties wish to carry out joint marketing, market development fund (\"MDF\") and event-support activities without setting up a full vendor program on PartnerWAV. The parties agree as follows."
 ],
 "sections": [
  {"title": "Purpose and scope", "clauses": [
    "The parties will work together on the marketing activities described in Schedule A (the \"Activities\"): {{campaign}}.",
    "This Agreement is {{exclusivity}}: it does not stop either party from marketing with others unless Schedule A says so.",
    "Relationship to a Vendor Program Agreement. Where {{partyName}} also has a Vendor Program Agreement with CloudWAV, this Agreement sits alongside it and does not replace, duplicate or conflict with its marketing-materials terms: commission and override under that agreement do not apply to leads generated here, and MDF is a separate cost from commission. Where there is no Vendor Program Agreement, this Agreement is the only contract between the parties for these activities and creates no commission, override or reseller relationship."
  ]},
  {"title": "Term", "clauses": [
    "This Agreement starts on the Effective Date and runs for {{termMonths}} months. It may be extended by written agreement.",
    "Either party may end it early on {{noticeDays}} days' written notice."
  ]},
  {"title": "Each party's commitments", "clauses": [
    "CloudWAV will: {{cloudwavCommitment}}.",
    "{{partyName}} will: {{partyCommitment}}.",
    "Each party will carry out its part of the Activities with reasonable skill and care. Key dates and milestones are in Schedule A, and a party that expects to miss one will tell the other promptly."
  ]},
  {"title": "Marketing development fund", "clauses": [
    "Fund. The parties commit these budgets to the Activities: CloudWAV {{cloudwavFund}} and {{partyName}} {{partyFund}}, in {{currency}} (together the \"Fund\").",
    "Proposal first. The Fund is spent by proposal, not freely. Before an activity, the spending party sends a short proposal describing the activity, date, expected audience and cost breakdown. The other party approves or rejects it within {{approvalDays}} business days.",
    "Claim window. After the activity, the spending party submits its claim within {{claimDays}} days of completion, with itemized receipts, supplier invoices and proof of performance such as attendee lists or campaign metrics. Claims made later than that may be refused.",
    "Reimbursement. An approved claim is reimbursed within {{reimburseDays}} days of receipt. If the documents are incomplete, the reimbursing party says so within 10 days and the period runs from when they are completed.",
    "Eligible expenses. Only the expense categories listed as eligible in Schedule B are reimbursable, up to any cap stated there.",
    "No carry-over. Budget not used by the end of the term lapses and does not carry over."
  ]},
  {"title": "Campaigns and lead sharing", "clauses": [
    "Each party keeps the leads that come directly from its own channels and lists.",
    "A lead sourced jointly belongs to the party with an existing relationship with that customer; if neither has one, the parties share it equally and agree who follows up.",
    "Neither party will use the other's leads for anything other than follow-up on the Activity that produced them."
  ]},
  {"title": "Brand use and co-branding", "clauses": [
    "Each party grants the other a limited, non-exclusive license for the term to use its names, logos and brand guidelines in the co-marketing materials for the Activities.",
    "All co-branded materials need both parties' approval before publication. Each party will respond to a request for approval within {{reviewDays}} business days.",
    "Co-branded materials show both parties' names and logos with similar prominence. Neither party will alter the other's marks, suggest an exclusive relationship or a wider endorsement, or create confusion about who supplies a product.",
    "The license ends when this Agreement ends. Materials already published in print need not be recalled, but neither party will reprint or republish them."
  ]},
  {"title": "Performance and reporting", "clauses": [
    "Each party reports on the Activities it runs: event attendance and profile, webinar registrations and attendance, impressions and engagement for digital campaigns, email open and click rates, and the number and quality of leads.",
    "Reports are provided {{reportingFrequency}} and on completion of each Activity.",
    "If an Activity falls well short of the targets in Schedule D, either party may ask for a review, and the parties will adjust the next Activity in good faith."
  ]},
  {"title": "Confidentiality", "clauses": [
    "Neither party will disclose the other's pricing, product roadmap, customer lists or the financial terms of this Agreement.",
    "The existence of the collaboration and each party's presence at a public event are not confidential, and either party may mention the collaboration in its marketing.",
    "These obligations continue for {{confidentialityYears}} years after this Agreement ends."
  ]},
  {"title": "Data and lead handling", "clauses": [
    "Personal data collected through the Activities is handled under the privacy laws that apply, including the GDPR, the CCPA and Thailand's PDPA where relevant.",
    "The party that collects participant data may use it for follow-up on the topic of that Activity only. It will not sell it, share it for unrelated marketing or add it to third-party databases without consent.",
    "Leads are owned by the party with the first-party relationship. The other party has only the limited right to use them stated in clause 5."
  ]},
  {"title": "Intellectual property", "clauses": [
    "Each party keeps the rights in its own marks, content and materials. Jointly created campaign materials may be used by both parties for the Activities during the term, and afterwards only with the other's consent."
  ]},
  {"title": "Term and termination: wind-down", "clauses": [
    "On early termination, budget not yet committed to an approved proposal is released and is not paid out.",
    "Activities already approved and under way are completed, and claims for them are reimbursed, unless the parties agree otherwise.",
    "Either party may terminate immediately for material breach not cured within 15 days of written notice."
  ]},
  {"title": "Limitation of liability", "clauses": [
    "Neither party is liable to the other for indirect or consequential loss or loss of profit.",
    "Each party's total liability under this Agreement is limited to the amount of the Fund it committed, except for breach of confidentiality, misuse of the other's brand or data, and liability that cannot be limited by law."
  ]},
  {"title": "Dispute resolution and governing law", "clauses": DISPUTES},
  {"title": "General", "clauses": GENERAL}
 ],
 "schedules": [
  {"title": "Schedule A -- Campaign details", "rows": [
    ["Activities", "{{campaign}}"], ["Timeline and milestones", "{{timeline}}"], ["Expected audience, venue or platform", "{{audience}}"],
    ["CloudWAV commitment", "{{cloudwavCommitment}}"], ["{{partyName}} commitment", "{{partyCommitment}}"],
    ["Budgets", "CloudWAV {{cloudwavFund}}; {{partyName}} {{partyFund}} ({{currency}})"], ["Portal record", "{{portalTerms}}"]]},
  {"title": "Schedule B -- MDF expense categories", "rows": [
    ["Eligible", "Event sponsorship (booth, speaking slot, attendee passes); print production of co-branded collateral; digital advertising promoting the collaboration; joint webinars and virtual events (platform, speaker fees); co-sent email campaigns or limited list rental; trade show and conference passes and logistics."],
    ["Not eligible", "Product development or engineering; sales salaries or commissions; either party's own staff time; general overhead; expenses that benefit only one party; food and drink outside an event or above an agreed per-head limit; travel and accommodation, except for event speakers where agreed; purchase of contact lists."],
    ["Caps", "{{mdfCaps}}"]]},
  {"title": "Schedule C -- Brand usage guidelines", "rows": [
    ["Approval", "Both parties, within {{reviewDays}} business days."], ["Attribution", "Both names and logos with similar prominence; each party's own brand guidelines apply to its marks."]]},
  {"title": "Schedule D -- Performance targets", "rows": [
    ["Targets", "{{targets}}"], ["Reporting", "{{reportingFrequency}} and on completion of each Activity."]]}
 ],
 "html": [],
 "fields": F({
  "campaign": {"label": "The marketing activities"},
  "timeline": {"label": "Timeline and milestones"},
  "audience": {"label": "Expected audience, venue or platform"},
  "cloudwavCommitment": {"label": "What CloudWAV will do"},
  "partyCommitment": {"label": "What they will do"},
  "cloudwavFund": {"label": "CloudWAV budget"},
  "partyFund": {"label": "Their budget"},
  "currency": {"label": "Currency", "def": "USD"},
  "exclusivity": {"label": "Exclusivity", "def": "non-exclusive"},
  "termMonths": {"label": "Term (months)", "def": "12"},
  "noticeDays": {"label": "Early termination notice (days)", "def": "30"},
  "approvalDays": {"label": "Proposal approval (business days)", "def": "5"},
  "claimDays": {"label": "Claim window (days)", "def": "30"},
  "reimburseDays": {"label": "Reimbursement (days)", "def": "30"},
  "reviewDays": {"label": "Brand review (business days)", "def": "3"},
  "reportingFrequency": {"label": "Reporting frequency", "def": "monthly"},
  "confidentialityYears": {"label": "Confidentiality period (years)", "def": "2"},
  "mdfCaps": {"label": "Per-item caps", "def": "As stated in each approved proposal"},
  "targets": {"label": "Performance targets"}
 }),
 "doc": {"partyName": "[Marketing Partner name]", "portalTerms": "[As recorded in PartnerWAV]"}
}

# ================================================================== 4. Reseller Agreement
T["Partner Reseller Agreement"] = {
 "title": "PartnerWAV Reseller Agreement",
 "file": "PartnerWAV_Reseller_Agreement",
 "summary": "The master agreement a Partner (MSP, VAR, telco or affiliate) signs once, covering every Program it then joins.",
 "note": NOTE,
 "parties": [
  "This Reseller Agreement (the \"Agreement\") is made on {{effectiveDate}} between:",
  "(1) {{cloudwavEntity}} (\"CloudWAV\"); and",
  "(2) {{partyEntity}} (\"{{partyName}}\" or the \"Partner\").",
  "CloudWAV operates the PartnerWAV platform, on which vendors run partner programs (each a \"Program\"). The Partner is a reseller, managed service provider, value-added reseller, telco, affiliate or referral partner that wishes to enroll in one or more Programs. The parties agree as follows."
 ],
 "sections": [
  {"title": "Purpose and scope", "clauses": [
    "This Agreement sets the terms on which the Partner enrolls in Programs on PartnerWAV and markets, refers or resells the vendors' products. CloudWAV operates the platform, tracks deals and commission, pays the Partner what it has earned and helps resolve disputes between the Partner and vendors.",
    "The Partner is authorized to sell in {{territory}}, unless a Program states a different territory in Schedule A. The tiers the Partner can hold (Affiliate / Referral, Reseller, Channel Manager) are defined by each Program, and the Partner's tier in each is recorded in Schedule A.",
    "Where the Partner also has a Custom Marketing Agreement with CloudWAV, this Agreement sits alongside it and does not replace it."
  ]},
  {"title": "One account, many programs", "clauses": [
    "This is a master agreement. The Partner signs it once at enrollment, and it governs every Program the Partner joins afterwards.",
    "Each Program the Partner joins is added as a row in Schedule A through the PartnerWAV portal and needs no new signature. Schedule A as shown in the Partner's PartnerWAV account at any time is the current Schedule A.",
    "The same Partner protections, payment terms and support apply across all Programs. Only the economics vary by vendor."
  ]},
  {"title": "Partner profile", "clauses": [
    "Published profile. The Partner's company name, country, tagline, specialties, credentials, past projects and contact person for vendors are shown in the Partner Network and to vendors. The Partner may edit them at any time and confirms they are accurate.",
    "Non-published details. The Partner's legal name, phone, email, address, bank and payment details, tax ID and any insurance details are visible only to the Partner and CloudWAV. They are not published and are not shared with vendors unless the Partner agrees or a payment or legal requirement needs it.",
    "Changes to payment or tax details are verified by CloudWAV before they take effect. Schedule B lists the published and non-published fields."
  ]},
  {"title": "Enrollment in programs", "clauses": [
    "The Partner chooses a Program and tier in the portal, reads the Program's terms and enrolls. Open tiers are available immediately.",
    "For restricted tiers the vendor may ask for company information or references and will approve or decline within 5 business days.",
    "Once enrolled, the Partner has access to that vendor's Resource Library, commission tracking, deal registration for Reseller and Channel Manager tiers, and the Channel Manager tools where it holds that tier."
  ]},
  {"title": "Commission, override and payment", "clauses": [
    "The Partner earns commission on its sales and referrals at the rate for its tier in each Program.",
    "Incorporated by reference. The commission and override rates of a Program are those in that Program's economics schedule under the vendor's Vendor Program Agreement with CloudWAV. They are incorporated into this Agreement by reference and are not restated here, so the figures live in one place. They are shown to the Partner in the portal before it enrolls. If a vendor changes its rates, the change applies to deals registered after the Partner is notified, not to deals already registered.",
    "Where the Partner holds a Channel Manager tier, it also earns the Program's override on the sales of the sub-resellers it recruited. The override is paid on top of the sub-reseller's commission, never out of it.",
    "CloudWAV pays commission and override within {{payoutDays}} days after the end of the month in which the vendor's payment for the sale was received, on the same schedule for every Program.",
    "The Partner chooses one payout currency: {{payoutCurrency}}. Amounts earned in other currencies are converted at the mid-market rate on the payment date, and CloudWAV bears the conversion fee.",
    "CloudWAV applies any withholding tax the law requires and gives the Partner the certificate. The Partner provides its tax ID and any documents needed for treaty relief. Each party is responsible for its own income taxes.",
    "If a customer is refunded, the related commission may be deducted from the next payment. Commission statements are available in the portal; the Partner should raise any query within 60 days of a statement."
  ]},
  {"title": "Deal registration and platform use: non-circumvention", "clauses": [
    "In Reseller and Channel Manager tiers, the Partner registers each qualified deal in the portal, with the customer's name, the expected value and close date and scoping notes, before proposing to the customer.",
    "The vendor may challenge a registration within the period stated for the Program (5 business days unless stated otherwise) for a conflict with an existing deal or customer. If it does not, the deal is approved.",
    "An approved deal is protected for the Program's protection period. If the customer buys within that period, the Partner earns the commission whichever channel takes the order.",
    "Non-circumvention. The Partner is free to use the Partner Network and direct messaging to reconnect with, coordinate with and work alongside other partners; nothing in this clause restricts partners from knowing or working with each other. The Partner will not, however, deliberately route a registered deal around deal registration and commission. If it does, it forfeits its commission on that deal. CloudWAV may in future offer a paid tier for posting reseller projects or staffing requests on the Partner Network; this Agreement sets no terms for it, and any such tier would be offered on separate terms the Partner may accept or decline.",
    "The Partner will tell CloudWAV if a customer is owned or controlled by the Partner or its owners. The vendor may require approval or apply different terms to such deals.",
    "Protection periods, processing times and the conflict process for each Program are summarized in Schedule C."
  ]},
  {"title": "Community guidelines", "clauses": [
    "The Partner may use the Partner Network, community groups, the industry feed and training for its business: finding collaborators, sharing project results with customer names removed, asking for staffing or subcontractor referrals, and coordinating sales and delivery.",
    "The Partner will not: harass, threaten or discriminate against others; send spam or promotion outside the channels meant for it; post customers' personal data, pricing or deal terms without the customer's consent; copy, scrape or reverse-engineer the platform or other partners' profiles; or misstate its credentials or past projects.",
    "CloudWAV may warn the Partner, suspend its account or, for serious or repeated breaches, terminate this Agreement."
  ]},
  {"title": "Confidentiality and data", "clauses": [
    "CloudWAV holds the Partner's profile, commission history and deal history. A vendor can see the Partner's published profile and, for its own Program only, the Partner's enrollment, commission statements and deal history. A vendor cannot see the Partner's results with other vendors or its non-published details.",
    "The Partner will keep vendors' pricing, training materials and customer lists confidential and will not share them with anyone not enrolled in the Program.",
    "The Partner is responsible for protecting the end-customer data it collects and for complying with the privacy laws that apply to it.",
    "Confidentiality obligations continue for {{confidentialityYears}} years after the Partner leaves a Program or this Agreement ends."
  ]},
  {"title": "Training and certification", "clauses": [
    "A Program may require the Partner to complete training or certification before it registers deals. The requirement is shown in the Program's terms.",
    "The Partner's certifications are recorded by CloudWAV and shown on its profile. A vendor may update its curriculum and require recertification within a reasonable period, normally 30 days."
  ]},
  {"title": "Term and termination", "clauses": [
    "This Agreement has no fixed term. It continues until terminated under this clause.",
    "Leaving a Program. The Partner may leave a Program at any time on 30 days' notice, or immediately if it has no active registered deals. After leaving it can register no new deals in that Program; deals already registered stay commissionable until they close or their protection ends, and commission already earned is paid.",
    "The Partner may terminate this Agreement at any time on {{partnerNoticeDays}} days' written notice.",
    "CloudWAV may terminate this Agreement on {{cloudwavNoticeDays}} days' written notice if the Partner materially breaches it, no longer operates as a reseller, service provider or affiliate, or becomes insolvent. CloudWAV may suspend the account immediately where needed to protect others on the platform.",
    "On termination the Partner leaves all Programs and loses access to its account. Commission on deals registered before termination continues to be paid when those deals close. Vendors have 30 days to arrange handover of the Partner's open deals."
  ]},
  {"title": "Limitation of liability", "clauses": [
    "CloudWAV is not liable for a vendor's acts or omissions, including a vendor's failure to pay, the quality of its products or its service levels. CloudWAV will use reasonable efforts to recover commission a vendor owes the Partner.",
    "CloudWAV is responsible for its own commission processing errors, which it will correct within 30 days of being told; for keeping the platform available, with a target of 99.5% uptime; and for unauthorized access to the Partner's confidential information caused by CloudWAV's failure.",
    "Neither party is liable for indirect or consequential loss or loss of profit. Each party's total liability under this Agreement is limited to the greater of the commission paid to the Partner in the 12 months before the claim and {{liabilityFloor}}.",
    "The Partner indemnifies CloudWAV against third-party claims arising from the Partner's misrepresentation, breach of confidentiality or breach of the community guidelines."
  ]},
  {"title": "Dispute resolution and governing law", "clauses": [
    "Disputes with a vendor. If the Partner and a vendor disagree about a commission amount, a deal conflict or a rejected registration, either may refer it to CloudWAV. CloudWAV reviews both sides' evidence and gives its determination within 15 business days. If the Partner or the vendor does not accept the determination, either may take the matter to mediation, sharing the cost equally."
  ] + DISPUTES},
  {"title": "General", "clauses": GENERAL}
 ],
 "schedules": [
  {"title": "Schedule A -- Programs enrolled", "rows": [
    ["Programs at the date of this Agreement", "{{programsTable}}"],
    ["Later programs", "Added through the PartnerWAV portal when the Partner enrolls; no new signature needed."],
    ["Commission", "Per each Program's economics schedule under its Vendor Program Agreement, incorporated by reference and shown in the portal."]]},
  {"title": "Schedule B -- Partner profile", "rows": [
    ["Published profile", "Company name: {{partyName}}. Country: {{partnerCountry}}. Tagline, specialties, credentials, past projects and vendor contact as shown on the Partner's PartnerWAV profile."],
    ["Contact details (not published)", "Legal name, phone, email and address; bank and payment details; tax ID; insurance details. Visible to the Partner and CloudWAV only."]]},
  {"title": "Schedule C -- Deal registration and non-circumvention", "rows": [
    ["Vendor response", "5 business days unless the Program states otherwise."], ["Protection period", "As stated for each Program and tier (typically 30 to 90 days)."],
    ["Conflicts", "Earlier approved registration prevails; CloudWAV determines disputes within 15 business days."], ["After leaving a Program", "Registered deals stay commissionable until they close or protection ends."]]}
 ],
 "html": ["programsTable"],
 "fields": F({
  "territory": {"label": "Territory the Partner sells in"},
  "payoutDays": {"label": "Payout (days after month end)", "def": "30"},
  "payoutCurrency": {"label": "Payout currency", "def": "USD"},
  "confidentialityYears": {"label": "Confidentiality period (years)", "def": "2"},
  "partnerNoticeDays": {"label": "Partner's notice to terminate (days)", "def": "30"},
  "cloudwavNoticeDays": {"label": "CloudWAV's notice to terminate (days)", "def": "60"},
  "liabilityFloor": {"label": "Liability floor", "def": "USD 50,000"}
 }),
 "doc": {"partyName": "[Partner name]", "partnerCountry": "[Country]",
  "programsTable": [["Program", "Tier", "Commission", "Enrolled"], ["[Program]", "[Tier]", "Per the Program's economics schedule", "[Date]"], ["", "", "", ""]]}
}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "js"
    if mode == "json":
        print(json.dumps(T, ensure_ascii=False))
    else:
        portal = {k: {x: v[x] for x in ("title", "note", "parties", "sections", "schedules", "html", "fields")} for k, v in T.items()}
        js = "  var AGR_TEMPLATE_TEXT = " + json.dumps(portal, ensure_ascii=False, indent=1) + ";\n"
        assert not any(c in js for c in "‘’“”—–"), "curly quote or long dash in template text"
        sys.stdout.write(js)
