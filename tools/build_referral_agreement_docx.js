// Builds the Word version of the Software Project Referral Agreement from the template in
// partnerwav-v11-merged.html (SRA_TEMPLATE + DEFAULT_REFERRAL_TERMS), with the default terms.
// Usage: node tools/build_referral_agreement_docx.js [out.docx]
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, AlignmentType, Footer, PageNumber } = require("docx");
const html = fs.readFileSync(path.join(__dirname, "..", "partnerwav-v11-merged.html"), "utf8");
const block = html.slice(html.indexOf("/*SRA-START*/"), html.indexOf("/*SRA-END*/"));
const termsSrc = html.slice(html.indexOf("var DEFAULT_REFERRAL_TERMS"), html.indexOf("};", html.indexOf("var DEFAULT_REFERRAL_TERMS")) + 2);
const SRA_TEMPLATE = new Function(block + "; return SRA_TEMPLATE;")();
const T = new Function(termsSrc + "; return DEFAULT_REFERRAL_TERMS;")();
const money = n => "THB " + Number(n).toLocaleString("en-US");
const v = {
  effectiveDate: "____________", cloudwavEntity: "CloudWAV [legal entity name, registration no., address]",
  houseName: "[Software house legal name]", houseAddressText: " of [address]",
  referralRate: T.referralRate, windowMonths: T.windowMonths, stepDownRate: T.stepDownRate, stepDownMonths: T.stepDownMonths,
  cosellRate: T.cosellRate, cosellMonths: T.cosellMonths, resellDiscount: T.resellDiscount,
  vendorReferralRate: T.vendorReferralRate, vendorReferralMonths: T.vendorReferralMonths,
  advisoryShareRate: T.advisoryShareRate, advisoryShareMonths: T.advisoryShareMonths, originatorShareRate: T.originatorShareRate, originatorMonths: T.originatorMonths,
  maintenanceText: T.maintenanceHalf ? "half the applicable rate" : "the full applicable rate",
  minFeeText: T.minFee ? "The minimum fee for each won Project is " + money(T.minFee) + ". " : "",
  capText: T.capPerYear ? "Fees for any one Client are capped at " + money(T.capPerYear) + " per 12 months." : "There is no minimum fee and no cap.",
  minFeeSchedule: T.minFee ? money(T.minFee) : "None", capSchedule: T.capPerYear ? money(T.capPerYear) + " per Client per 12 months" : "None",
  acceptDays: T.acceptDays, protectionMonths: T.protectionMonths, tailMonths: T.tailMonths, paymentDays: T.paymentDays, clawbackDays: T.clawbackDays,
  currency: T.currency, termMonths: T.termMonths, noticeDays: T.noticeDays,
  governingLaw: "the laws of Thailand", disputeText: "the dispute will be settled by arbitration in Bangkok under the Arbitration Rules of the Thai Arbitration Institute, in English.",
  houseContact: "____________", cloudwavContact: "partners@cloudwav.com (to be confirmed)"
};
const fill = s => String(s).replace(/\{\{(\w+)\}\}/g, (_, k) => v[k] != null ? v[k] : "{{" + k + "}}");
const P = (text, opts = {}) => new Paragraph({ spacing: { after: 120, line: 300 }, ...opts, children: Array.isArray(text) ? text : [new TextRun(text)] });
const border = { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB" };
const cellBorders = { top: border, bottom: border, left: border, right: border };
const W = 9026, C1 = 3200, C2 = W - C1; // A4 text width in DXA
const tableOf = rows => new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2],
  rows: rows.map(r => new TableRow({ children: [
    new TableCell({ width: { size: C1, type: WidthType.DXA }, borders: cellBorders, shading: { type: ShadingType.CLEAR, fill: "F2F2F7", color: "auto" }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ children: [new TextRun({ text: r[0], bold: true, size: 20 })] })] }),
    new TableCell({ width: { size: C2, type: WidthType.DXA }, borders: cellBorders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ children: [new TextRun({ text: fill(r[1]), size: 20 })] })] })
  ] })) });
const children = [
  new Paragraph({ heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun(SRA_TEMPLATE.title)] }),
  new Paragraph({ spacing: { after: 240 }, shading: { type: ShadingType.CLEAR, fill: "FFF4D6", color: "auto" }, children: [new TextRun({ text: SRA_TEMPLATE.note, italics: true, size: 20 })] }),
  ...SRA_TEMPLATE.parties.map(x => P(fill(x)))
];
SRA_TEMPLATE.sections.forEach((s, i) => {
  children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun((i + 1) + ". " + s.title)] }));
  s.clauses.forEach((c, j) => { const t = fill(c).trim(); if (t) children.push(P([new TextRun({ text: (i + 1) + "." + (j + 1) + "  ", bold: true }), new TextRun(t)])); });
});
children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 320, after: 120 }, pageBreakBefore: true, children: [new TextRun("Schedule A -- Commercial terms")] }));
children.push(tableOf(SRA_TEMPLATE.schedule));
children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 320, after: 120 }, children: [new TextRun("Signatures")] }));
children.push(tableOf([["For CloudWAV", "Name:            Title:           Date:"], ["For the Developer", "Name:            Title:           Date:"]]));
const doc = new Document({
  creator: "CloudWAV", title: SRA_TEMPLATE.title,
  styles: { default: { document: { run: { font: "Calibri", size: 22 } } } },
  sections: [{ properties: { page: { margin: { top: 1300, bottom: 1300, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Software Project Referral Agreement -- draft for review -- page ", size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "888888" })] })] }) },
    children }]
});
const out = process.argv[2] || "Software-Project-Referral-Agreement.docx";
Packer.toBuffer(doc).then(b => { fs.writeFileSync(out, b); console.log("wrote", out, b.length, "bytes"); });
