# PartnerWAV Deployment Checklist

## Before Every Commit

### Layer 1: Pre-commit Hook (Automatic)
- [ ] Pre-commit hook checks for curly quotes
- [ ] If hook rejects: Run `python3 fix_quotes.py index.html` to fix
- [ ] Commit again

### Layer 2: Local Testing
- [ ] Open `index.html` in browser
- [ ] Test all menus work correctly
- [ ] Test Partner > Create Lead modal form (Decision 10)
- [ ] Test Partner > Edit Lead functionality with status dropdown
- [ ] Test Partner > Convert to Deal navigation
- [ ] Test Partner > Deals view displays correctly
- [ ] Test SOW Builder modal form (Decision 11)
- [ ] Check browser console for JavaScript errors (F12 > Console)

## After Every Push to GitHub

### Layer 3: GitHub Actions (Automatic)
- [ ] Visit https://github.com/mpower-source/partnerwav/actions
- [ ] Verify latest workflow run shows ✓ (green checkmarks)
- [ ] If red ✗ appears, click the workflow and see error details

### Layer 4: GitHub Pages Deployment
- [ ] Wait 60 seconds for GitHub Pages to rebuild
- [ ] Hard refresh: **Ctrl+Shift+R** (Windows) or **Cmd+Shift+R** (Mac)
- [ ] Visit https://mpower-source.github.io/partnerwav/
- [ ] Repeat Layer 2 tests on deployed version
- [ ] If menus don't work: Check browser console for errors

## Critical Rules

❌ **NEVER commit files with:**
- Curly double quotes: " "
- Curly single quotes: ' '
- Em dashes: —

✅ **ALWAYS use:**
- Straight double quotes: " "
- Straight single quotes: ' '
- Hyphens: - or --

## Quick Fixes

**If curly quotes appear in newly added code:**
```bash
python3 fix_quotes.py index.html
git add index.html
git commit -m "Fix: Remove curly quotes"
git push origin main
```

**If menus break after push:**
1. Hard refresh browser (Ctrl+Shift+R)
2. Wait 60 seconds for GitHub Pages to rebuild
3. Check browser console (F12) for errors
4. Run fix_quotes.py to check for hidden curly quotes

**To verify no curly quotes in file:**
```bash
python3 << 'PYEOF'
with open("index.html", encoding="utf-8") as f:
    content = f.read()
    if any(c in content for c in '“”‘’—'):
        print("❌ Curly quotes found!")
    else:
        print("✓ File is clean!")
PYEOF
```
