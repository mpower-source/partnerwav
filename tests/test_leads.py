from harness import *
import json, datetime

today = datetime.date.today().isoformat()

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "partner"); nav(pg, "partner-my-leads")
    start = pg.locator("#leadsList [data-edit-lead]").count()

    # ----- create a lead
    pg.click('[data-goto-screen="leads-editor"]'); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-leads-editor"], "Create a lead opens the form")
    ok(pg.get_attribute("#leadCreatedDate", "type") == "date", "Created date is a calendar picker")
    ok(pg.input_value("#leadCreatedDate") == today, "Created date starts on today")
    pg.click('#leadForm button[type="submit"]'); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-leads-editor"], "Doesn't save without the required fields")
    pg.fill("#leadProspectName", "Chiang Mai Clinic Group"); pg.fill("#leadValue", "$42,000"); pg.select_option("#leadStatus", "prospect")
    pg.fill("#leadNotes", "Met at the Bangkok MSP meetup"); pg.fill("#leadCreatedDate", "2026-09-30")
    pg.click('#leadForm button[type="submit"]'); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-partner-my-leads"], "Save Lead returns to My Leads")
    card = pg.locator("#leadsList .card").filter(has_text="Chiang Mai Clinic Group")
    ok(card.count() == 1, "The new lead shows in My Leads")
    ok("30 Sept 2026" in card.inner_text() or "30 Sep 2026" in card.inner_text(), "Shows the created date")
    ok(pg.locator("#leadsList [data-edit-lead]").count() == start + 1, "One more lead in the list")

    # ----- kept after reload
    pg.reload(); pg.wait_for_timeout(700); role(pg, "partner"); nav(pg, "partner-my-leads")
    ok(pg.locator("#leadsList .card").filter(has_text="Chiang Mai Clinic Group").count() == 1, "Lead is kept after reload")
    saved = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_leads')"))
    mine = [l for l in saved if l["prospectName"] == "Chiang Mai Clinic Group"][0]
    ok(mine["partnerId"] and mine["createdDate"] == "2026-09-30", "Saved for this partner with the picked date")

    # ----- edit opens the same form, filled in
    pg.locator("#leadsList .card").filter(has_text="Chiang Mai Clinic Group").locator("[data-edit-lead]").click(); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-leads-editor"] and pg.input_value("#leadProspectName") == "Chiang Mai Clinic Group" and pg.input_value("#leadCreatedDate") == "2026-09-30", "Edit opens the form with the lead's details")
    pg.select_option("#leadStatus", "qualified"); pg.click('#leadForm button[type="submit"]'); pg.wait_for_timeout(300)
    ok("QUALIFIED" in pg.locator("#leadsList .card").filter(has_text="Chiang Mai Clinic Group").inner_text().upper(), "Edit saves")

    # ----- an older lead with a text date can be given a real date
    first = pg.locator("#leadsList .card").filter(has_text="Bangkok Bank Holdings")
    if first.count():
        first.locator("[data-edit-lead]").click(); pg.wait_for_timeout(300)
        ok(pg.input_value("#leadCreatedDate") == "" and "2 weeks ago" in pg.inner_text("#leadCreatedNote"), "Older text dates are shown so they can be replaced")
        pg.click('#leadForm [data-back-screen="partner-my-leads"]'); pg.wait_for_timeout(200)

    # ----- Create after an edit opens a blank form
    pg.click('[data-goto-screen="leads-editor"]'); pg.wait_for_timeout(300)
    ok(pg.input_value("#leadProspectName") == "" and pg.input_value("#leadCreatedDate") != "", "Create a lead after editing opens a blank form")
    pg.click('#leadForm [data-back-screen="partner-my-leads"]'); pg.wait_for_timeout(200)

    # ----- archive
    pg.locator("#leadsList .card").filter(has_text="Chiang Mai Clinic Group").locator("[data-edit-lead]").click(); pg.wait_for_timeout(300)
    pg.click("#deleteLeadBtn"); pg.wait_for_timeout(300)
    ok(pg.locator("#leadsList .card").filter(has_text="Chiang Mai Clinic Group").count() == 0, "Archived lead leaves the list")
    b.close()
report()
