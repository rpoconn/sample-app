import { expect, type Page, test } from "@playwright/test"

import {
    changeCompanyIds,
    createCompanyWithPlan,
    createUserInCompany,
    idOf,
    savedCompanyIds,
    savedUserIds,
    searchFor,
    setUserIds,
    subtreeSwitchFor,
    switchFor,
    waitForGrid,
} from "./utils/jurisdictions"
import { logInUser } from "./utils/user"

const TEXAS = "United States / States / Texas"
const WYOMING = "United States / States / Wyoming"

// The tabs' accessible names are their tooltips, so match the label
const statusTab = (page: Page, label: string) =>
    page
        .getByRole("tablist", { name: "Filter by status" })
        .getByRole("tab")
        .filter({ hasText: new RegExp(`^${label}`) })

// The row count shown inside a status tab
const tabCount = async (page: Page, label: string) =>
    Number(await statusTab(page, label).locator("span").last().textContent())

// Each test gets its own company and users, so tests can change the license and
// selections freely and run in parallel
test.use({ storageState: { cookies: [], origins: [] } })

test.describe("User scope", () => {
    test("Shows the personal scope and what the license leaves out", async ({
        page,
    }) => {
        const { company } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        await expect(
            page.getByRole("heading", { name: "Jurisdictions" }),
        ).toBeVisible()
        await expect(
            page.getByText("These are your personal jurisdictions"),
        ).toBeVisible()
        // Nothing picked yet, and the license leaves some out
        await expect(statusTab(page, "Enabled")).toHaveText(/^Enabled\s*0$/)
        expect(await tabCount(page, "Disabled")).toBeGreaterThan(0)

        // Outside the plan: visible, but locked
        for (const name of ["Wyoming", "Utah", "Los Angeles"]) {
            await searchFor(page, name)
            await expect(
                switchFor(page, `Enable ${name} for me`),
            ).toBeDisabled()
            await expect(
                page
                    .getByRole("grid")
                    .getByRole("img", { name: /^Not enabled for your license/ })
                    .first(),
            ).toBeVisible()
        }

        // In the plan: selectable
        for (const name of ["San Francisco", "Texas"]) {
            await searchFor(page, name)
            await expect(switchFor(page, `Enable ${name} for me`)).toBeEnabled()
        }
    })

    test("Turning on a jurisdiction is saved", async ({ page }) => {
        const { company, tree } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        await searchFor(page, "Texas")
        await switchFor(page, "Enable Texas for me").click()
        await expect(switchFor(page, "Enable Texas for me")).toBeChecked()
        await expect
            .poll(() => savedUserIds(member))
            .toEqual([idOf(tree, TEXAS)])

        await page.reload()
        await searchFor(page, "Texas")
        await expect(switchFor(page, "Enable Texas for me")).toBeChecked()
    })

    test("Select all turns on a whole subtree", async ({ page }) => {
        const { company, tree, planIds } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        const canada = tree
            .filter((j) => j.name_path.startsWith("Canada / "))
            .filter((j) => planIds.includes(j.id))
            .map((j) => j.id)
            .sort()

        await subtreeSwitchFor(page, "Canada", "for me").click()
        await expect
            .poll(async () => (await savedUserIds(member)).sort())
            .toEqual(canada)
        await expect(subtreeSwitchFor(page, "Canada", "for me")).toBeChecked()
    })

    test("Select all skips locked jurisdictions and turns back off", async ({
        page,
    }) => {
        const { company, tree, planIds } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        const states = tree.filter((j) =>
            j.name_path.startsWith("United States / States / "),
        )
        const licensed = states
            .filter((j) => planIds.includes(j.id))
            .map((j) => j.id)
            .sort()

        const states_ = subtreeSwitchFor(page, "States", "for me")
        await states_.click()
        await expect
            .poll(async () => (await savedUserIds(member)).sort())
            .toEqual(licensed)
        expect(licensed).not.toContain(idOf(tree, WYOMING))
        // Locked states keep it short of fully on
        await expect(states_).not.toBeChecked()
        await expect(states_).toHaveAccessibleName(
            new RegExp(`\\(${licensed.length} of \\d+ on\\)`),
        )

        await states_.click()
        await expect.poll(() => savedUserIds(member)).toEqual([])
    })

    test("View selection shows the saved ids as JSON", async ({ page }) => {
        const { company, tree } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        const picks = [
            idOf(tree, TEXAS),
            idOf(tree, "Canada / Provinces / Ontario"),
        ]
        await setUserIds(member, picks)
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        await page.getByRole("button", { name: "View selection" }).click()
        const sheet = page.getByRole("dialog")
        await expect(sheet.getByText("Your selection")).toBeVisible()
        await expect(sheet.getByText("Texas")).toBeVisible()
        await expect(sheet.getByText("Ontario")).toBeVisible()

        await sheet.getByRole("tab", { name: "IDs (JSON)" }).click()
        await expect(
            sheet.getByText("GET /api/v1/users/me/jurisdictions"),
        ).toBeVisible()
        const json = JSON.parse(
            await sheet.getByTestId("selection-json").innerText(),
        )
        expect(json).toMatchObject({
            scope: "user",
            user_id: member.id,
            count: 2,
        })
        expect([...json.jurisdiction_ids].sort()).toEqual(
            (await savedUserIds(member)).sort(),
        )
    })

    test("Search and status filters narrow the rows", async ({ page }) => {
        const { company, tree } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await setUserIds(member, [idOf(tree, TEXAS)])
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        const grid = page.getByRole("grid")
        const everything = await tabCount(page, "All")

        // The tab counts follow the search
        await searchFor(page, "san")
        await expect(grid.locator("mark", { hasText: /san/i })).not.toHaveCount(
            0,
        )
        await expect.poll(() => tabCount(page, "All")).toBeLessThan(everything)
        expect(await tabCount(page, "All")).toBeGreaterThan(0)

        await page.getByRole("button", { name: "Clear filters" }).click()
        await expect(
            page.getByRole("textbox", { name: "Search jurisdictions" }),
        ).toHaveValue("")

        await statusTab(page, "Enabled").click()
        await expect(switchFor(page, "Enable Texas for me")).toBeVisible()
        await expect(switchFor(page, "Enable Ohio for me")).toHaveCount(0)

        await statusTab(page, "Disabled").click()
        await expect(switchFor(page, "Enable Texas for me")).toHaveCount(0)

        await statusTab(page, "All").click()
        await page
            .getByRole("textbox", { name: "Search jurisdictions" })
            .fill("zzzz-no-such-place")
        await expect(
            page.getByText("No jurisdictions match your filters"),
        ).toBeVisible()
        await page
            .getByRole("button", { name: "Clear filters" })
            .first()
            .click()
        await waitForGrid(page)
    })

    test("Expand all and collapse all", async ({ page }) => {
        const { company } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, member.email, member.password)
        await waitForGrid(page)

        const grid = page.getByRole("grid")
        await page.getByRole("button", { name: "Collapse all" }).click()
        await expect(
            grid.getByRole("button", { name: "Expand Canada" }),
        ).toBeVisible()
        await expect(
            grid.getByRole("button", { name: "Collapse Canada" }),
        ).toHaveCount(0)

        await page.getByRole("button", { name: "Expand all" }).click()
        await expect(
            grid.getByRole("button", { name: "Collapse Provinces" }),
        ).toBeVisible()
        await expect(switchFor(page, "Enable Alberta for me")).toBeVisible()
    })

    test("Members can't open the company admin page", async ({ page }) => {
        const { company } = await createCompanyWithPlan()
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, member.email, member.password)

        await page.goto("/company-admin")
        await expect(page).not.toHaveURL(/\/company-admin/)
        await expect(
            page.getByText("You're editing jurisdictions licenses"),
        ).toHaveCount(0)
    })
})

test.describe("Company scope", () => {
    test("Admins see the company scope", async ({ page }) => {
        const { company } = await createCompanyWithPlan()
        const admin = await createUserInCompany(company.id, "admin")
        await logInUser(page, admin.email, admin.password)

        await page.goto("/company-admin")
        await waitForGrid(page)
        await expect(
            page.getByText(
                "You're editing jurisdictions licenses for this company",
            ),
        ).toBeVisible()
        await expect(
            page.getByRole("columnheader", { name: "Users" }),
        ).toBeVisible()
    })

    test("Dropping a jurisdiction nobody uses saves without asking", async ({
        page,
    }) => {
        const { company, tree } = await createCompanyWithPlan()
        const admin = await createUserInCompany(company.id, "admin")
        await logInUser(page, admin.email, admin.password)
        await page.goto("/company-admin")
        await waitForGrid(page)

        await searchFor(page, "Texas")
        await switchFor(page, "Enable Texas for the company").click()
        await expect(page.getByRole("dialog")).toHaveCount(0)
        await expect
            .poll(() => savedCompanyIds(company.id))
            .not.toContain(idOf(tree, TEXAS))
    })

    test("Dropping a jurisdiction a member uses asks first", async ({
        page,
    }) => {
        const { company, tree } = await createCompanyWithPlan()
        const admin = await createUserInCompany(company.id, "admin")
        const member = await createUserInCompany(company.id, "member")
        const texas = idOf(tree, TEXAS)
        await setUserIds(member, [texas])
        await logInUser(page, admin.email, admin.password)
        await page.goto("/company-admin")
        await waitForGrid(page)

        await searchFor(page, "Texas")
        const texasSwitch = switchFor(page, "Enable Texas for the company")

        // Cancel keeps it for everyone
        await texasSwitch.click()
        const dialog = page.getByRole("dialog")
        await expect(dialog).toContainText(
            `Turn off Texas for all of ${company.name}?`,
        )
        await expect(
            dialog.getByRole("list", { name: "Affected users" }),
        ).toContainText(member.email)
        await dialog.getByRole("button", { name: "Cancel" }).click()
        await expect(dialog).toHaveCount(0)
        await expect(texasSwitch).toBeChecked()
        expect(await savedCompanyIds(company.id)).toContain(texas)
        expect(await savedUserIds(member)).toEqual([texas])

        // Confirming drops it from the company and the member
        await texasSwitch.click()
        await page
            .getByRole("dialog")
            .getByRole("button", { name: "Turn off for everyone" })
            .click()
        await expect
            .poll(() => savedCompanyIds(company.id))
            .not.toContain(texas)
        await expect.poll(() => savedUserIds(member)).toEqual([])
    })

    test("A license change while reviewing shows the latest first", async ({
        page,
    }) => {
        const { company, tree } = await createCompanyWithPlan()
        const admin = await createUserInCompany(company.id, "admin")
        const member = await createUserInCompany(company.id, "member")
        const texas = idOf(tree, TEXAS)
        const ontario = idOf(tree, "Canada / Provinces / Ontario")
        await setUserIds(member, [texas])
        await logInUser(page, admin.email, admin.password)
        await page.goto("/company-admin")
        await waitForGrid(page)

        await searchFor(page, "Texas")
        await switchFor(page, "Enable Texas for the company").click()
        const dialog = page.getByRole("dialog")
        await expect(dialog).toContainText(
            `Turn off Texas for all of ${company.name}?`,
        )

        // Someone else changes the license before this admin confirms
        await changeCompanyIds(company.id, { remove: [ontario] })
        await dialog
            .getByRole("button", { name: "Turn off for everyone" })
            .click()
        await expect(
            page.getByText(
                "The license changed while you were reviewing. Showing the latest.",
            ),
        ).toBeVisible()
        expect(await savedCompanyIds(company.id)).toContain(texas)

        // The review opens again on the latest license; confirming now commits
        await expect(dialog).toContainText(
            `Turn off Texas for all of ${company.name}?`,
        )
        await dialog
            .getByRole("button", { name: "Turn off for everyone" })
            .click()
        await expect
            .poll(() => savedCompanyIds(company.id))
            .not.toContain(texas)
        expect(await savedCompanyIds(company.id)).not.toContain(ontario)
        await expect.poll(() => savedUserIds(member)).toEqual([])
    })

    test("Licensing a jurisdiction lets members pick it", async ({
        page,
        browser,
    }) => {
        const { company, tree } = await createCompanyWithPlan()
        const admin = await createUserInCompany(company.id, "admin")
        const member = await createUserInCompany(company.id, "member")
        await logInUser(page, admin.email, admin.password)
        await page.goto("/company-admin")
        await waitForGrid(page)

        await searchFor(page, "Wyoming")
        await switchFor(page, "Enable Wyoming for the company").click()
        await expect
            .poll(() => savedCompanyIds(company.id))
            .toContain(idOf(tree, WYOMING))

        const memberContext = await browser.newContext({
            storageState: { cookies: [], origins: [] },
        })
        const memberPage = await memberContext.newPage()
        await logInUser(memberPage, member.email, member.password)
        await waitForGrid(memberPage)
        await searchFor(memberPage, "Wyoming")
        const wyoming = switchFor(memberPage, "Enable Wyoming for me")
        await expect(wyoming).toBeEnabled()
        await wyoming.click()
        await expect
            .poll(() => savedUserIds(member))
            .toEqual([idOf(tree, WYOMING)])
        await memberContext.close()
    })
})
