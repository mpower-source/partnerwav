// Builds the Word versions of the four PartnerWAV agreements from tools/agreement_templates.py (the same text the
// portal shows). Blanks to complete are shaded and in [brackets]; standard values are shaded so they are easy to find.
// Usage: node tools/build_agreement_docx.js [outDir]
const fs = require("fs"), path = require("path"), { execFileSync } = require("child_process");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  AlignmentType, Header, Footer, PageNumber, PageBreak } = require("docx");
const T = JSON.parse(execFileSync("python3", [path.join(__dirname, "agreement_templates.py"), "json"], { maxBuffer: 1 << 26 }).toString());
const outDir = process.argv[2] || ".";
const ACCENT = "3F22D6", SOFT = "EEEBFF", INK = "1B1830", HEAD = "Space Grotesk", BODY = "Inter";
const STATUS = "STATUS: DRAFT -- not for execution";
const W = 9360, C1 = 3000, C2 = W - C1;   // US Letter, 1 inch margins
const line = { style: BorderStyle.SINGLE, size: 4, color: "C9C4E8" }, borders = { top: line, bottom: line, left: line, right: line };
const pad = { top: 80, bottom: 80, left: 110, right: 110 };

function build(key){
  const t = T[key], doc = t.doc || {}, F = t.fields;
  const value = k => {
    if (doc[k] != null && !Array.isArray(doc[k])) return { text: String(doc[k]), fill: /\[/.test(String(doc[k])) };
    if (F[k]) return { text: F[k].def != null ? String(F[k].def) : "[" + F[k].label + "]", fill: true };
    throw new Error(key + ": no Word wording for {{" + k + "}}");
  };
  // text with {{placeholders}} -> runs; filled-in parts are shaded
  const runs = (text, base = {}) => {
    const out = []; let last = 0, m; const re = /\{\{(\w+)\}\}/g;
    while ((m = re.exec(text))){
      if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
      const v = value(m[1]);
      out.push(new TextRun({ text: v.text, ...base, ...(v.fill ? { shading: { type: ShadingType.CLEAR, fill: SOFT, color: "auto" } } : {}) }));
      last = re.lastIndex;
    }
    if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
    return out;
  };
  const P = (children, opts = {}) => new Paragraph({ spacing: { after: 120, line: 290 }, ...opts, children });
  const H = (text, opts = {}) => new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: 280, after: 120 }, ...opts, children: runs(text) });
  const cell = (children, w, shade) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders, margins: pad,
    ...(shade ? { shading: { type: ShadingType.CLEAR, fill: shade, color: "auto" } } : {}), children });
  const twoCol = rows => new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [C1, C2],
    rows: rows.map(r => new TableRow({ cantSplit: true, children: [
      cell([new Paragraph({ children: runs(r[0], { bold: true, size: 20 }) })], C1, "F6F5FC"),
      cell([new Paragraph({ children: runs(r[1], { size: 20 }) })], C2) ] })) });
  const grid = rows => { const n = rows[0].length, w = Math.floor(W / n), ws = rows[0].map((_, i) => i === n - 1 ? W - w * (n - 1) : w);
    return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: ws,
      rows: rows.map((r, ri) => new TableRow({ tableHeader: ri === 0, children: r.map((c, i) =>
        cell([new Paragraph({ children: [new TextRun({ text: c || " ", bold: ri === 0, size: 20, ...(ri > 0 && /\[/.test(c) ? { shading: { type: ShadingType.CLEAR, fill: SOFT, color: "auto" } } : {}) })] })], ws[i], ri === 0 ? SOFT : undefined)) })) }); };

  const body = [
    // ----- cover
    new Paragraph({ spacing: { before: 2400, after: 120 }, children: [new TextRun({ text: "PARTNERWAV", font: HEAD, bold: true, size: 22, color: ACCENT, characterSpacing: 60 })] }),
    new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: t.title.replace(/^PartnerWAV /, ""), font: HEAD, bold: true, size: 64, color: INK })] }),
    new Paragraph({ spacing: { after: 480 }, border: { top: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 12 } }, children: [new TextRun({ text: t.summary, size: 24, color: "4A4763" })] }),
    new Paragraph({ spacing: { after: 160 }, shading: { type: ShadingType.CLEAR, fill: SOFT, color: "auto" }, children: [new TextRun({ text: " " + STATUS + " ", font: HEAD, bold: true, size: 24, color: ACCENT })] }),
    P([new TextRun({ text: "This is a living draft. Its provisions are expected to change as the PartnerWAV platform develops, and it must be reviewed by counsel for both parties before it is signed.", size: 20, color: "4A4763" })]),
    P([new TextRun({ text: "How to complete it: shaded text in [brackets] is a blank to fill in for this agreement. Other shaded text is a standard value that can be changed. In the PartnerWAV portal these are filled in automatically from the program's settings.", size: 20, color: "4A4763" })]),
    new Paragraph({ spacing: { before: 1200 }, children: [new TextRun({ text: "CloudWAV  |  PartnerWAV agreement templates", size: 18, color: "7A7693" })] }),
    new Paragraph({ children: [new PageBreak()] }),
    // ----- agreement
    new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 200 }, children: [new TextRun(t.title)] }),
    ...t.parties.map(x => P(runs(x)))
  ];
  t.sections.forEach((s, i) => {
    body.push(H((i + 1) + ". " + s.title));
    s.clauses.forEach((c, j) => body.push(P([new TextRun({ text: (i + 1) + "." + (j + 1) + "\t", bold: true, color: ACCENT }), ...runs(c)], { indent: { left: 720, hanging: 720 }, tabStops: [{ type: "left", position: 720 }] })));
  });
  t.schedules.forEach((sc, si) => {
    body.push(H(sc.title, { pageBreakBefore: si === 0, spacing: { before: si === 0 ? 0 : 360, after: 140 } }));
    let buf = [];
    const flush = () => { if (buf.length){ body.push(twoCol(buf)); buf = []; } };
    sc.rows.forEach(r => {
      const m = /^\{\{(\w+)\}\}$/.exec(r[1]);
      if (m && Array.isArray(doc[m[1]])){ flush(); body.push(P(runs(r[0], { bold: true, size: 20 }), { spacing: { before: 160, after: 80 }, keepNext: true })); body.push(grid(doc[m[1]])); body.push(P([new TextRun("")], { spacing: { after: 60 } })); }
      else buf.push(r);
    });
    flush();
  });
  body.push(H("Signatures", { spacing: { before: 480, after: 140 } }));
  body.push(P([new TextRun("Signed by the parties' authorized representatives.")], { keepNext: true }));
  const party = (doc.partyName || "the other party").replace(/^the /, "the ");
  body.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W / 2, W / 2], rows: [
    new TableRow({ cantSplit: true, children: [["For CloudWAV"], ["For " + party]].map(x => cell([
      new Paragraph({ spacing: { after: 360 }, children: [new TextRun({ text: x[0], bold: true })] }),
      ...["Signature", "Name", "Title", "Date"].map(l => new Paragraph({ spacing: { after: 220 }, children: [new TextRun({ text: l + ":  ______________________________", size: 20 })] }))
    ], W / 2)) }) ] }));

  const mark = (extra) => new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: STATUS, font: HEAD, bold: true, size: 16, color: ACCENT }), ...extra] });
  return new Document({
    creator: "CloudWAV", title: t.title, description: t.summary,
    styles: {
      default: { document: { run: { font: BODY, size: 21, color: INK } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: HEAD, size: 34, bold: true, color: INK }, paragraph: { spacing: { before: 0, after: 200 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: HEAD, size: 25, bold: true, color: ACCENT }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } }
      ]
    },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1300, left: 1440, right: 1440 } } },
      headers: { default: new Header({ children: [mark([])] }) },
      footers: { default: new Footer({ children: [mark([new TextRun({ text: "   |   " + t.title + "   |   page ", size: 16, color: "7A7693" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "7A7693" }), new TextRun({ text: " of ", size: 16, color: "7A7693" }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "7A7693" })])] }) },
      children: body
    }]
  });
}
(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  for (const key of Object.keys(T)){
    const file = path.join(outDir, T[key].file + ".docx");
    fs.writeFileSync(file, await Packer.toBuffer(build(key)));
    console.log("wrote", file);
  }
})().catch(e => { console.error(e.message); process.exit(1); });
