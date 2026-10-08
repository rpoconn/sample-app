import { expect, type Locator, type Page } from "@playwright/test"

import {
    CompaniesService,
    type CompanyRole,
    JurisdictionsService,
    LoginService,
    PrivateService,
    type UserPublic,
    UsersService,
} from "../../src/client"
import { client } from "../../src/client/client.gen"
import { firstSuperuser, firstSuperuserPassword } from "../config.ts"
import { randomEmail, randomPassword } from "./random"

client.setConfig({
    baseURL: `${process.env.VITE_API_URL}`,
})

const bearer = (token: string) => ({ Authorization: `Bearer ${token}` })

let superuserToken: Promise<string> | undefined

// Shared by every test in a worker; the superuser never changes
function getSuperuserToken() {
    superuserToken ??= LoginService.loginAccessToken({
        body: { username: firstSuperuser, password: firstSuperuserPassword },
    }).then((r) => r.data.access_token)
    return superuserToken
}

// The PRD's sample plan: all of Canada, US National, every state but Wyoming and
// Utah, and only San Francisco among cities. Matches the seed in core/db.py.
function inPlan(namePath: string) {
    const [country, group, state, ...rest] = namePath.split(" / ")
    if (country === "Canada") return true
    if (country !== "United States") return false
    if (group === "National") return true
    if (group !== "States" || !state) return false
    if (state === "Wyoming" || state === "Utah") return false
    return rest[0] !== "Cities" || rest[1] === "San Francisco"
}

// A company of its own, so tests can change its license without touching others
export async function createCompanyWithPlan() {
    const headers = bearer(await getSuperuserToken())
    const { data: company } = await CompaniesService.createCompany({
        headers,
        body: { name: `Company ${Math.random().toString(36).substring(2)}` },
    })
    const { data: tree } = await JurisdictionsService.readJurisdictionTree({
        headers,
    })
    const planIds = tree.data
        .filter((j) => !j.is_structural && inPlan(j.name_path))
        .map((j) => j.id)
    await CompaniesService.setCompanyJurisdictions({
        headers,
        path: { company_id: company.id },
        body: { jurisdiction_ids: planIds },
    })
    return { company, planIds, tree: tree.data }
}

export type TestUser = UserPublic & { password: string }

export async function createUserInCompany(
    companyId: string,
    role: CompanyRole,
): Promise<TestUser> {
    const email = randomEmail()
    const password = `${randomPassword()}Aa1!`
    const { data: user } = await PrivateService.createUser({
        body: {
            email,
            password,
            full_name: `Test ${role}`,
            is_verified: true,
            company_id: companyId,
            company_role: role,
        },
    })
    return { ...user, password }
}

async function tokenFor(user: TestUser) {
    const { data } = await LoginService.loginAccessToken({
        body: { username: user.email, password: user.password },
    })
    return data.access_token
}

// What the API has saved, checked independently of what the page shows
export async function savedUserIds(user: TestUser) {
    const { data } = await UsersService.readMyJurisdictionIds({
        headers: bearer(await tokenFor(user)),
    })
    return data.jurisdiction_ids
}

export async function savedCompanyIds(companyId: string) {
    const { data } = await CompaniesService.readCompanyJurisdictionIds({
        headers: bearer(await getSuperuserToken()),
        path: { company_id: companyId },
    })
    return data.jurisdiction_ids
}

export async function setUserIds(user: TestUser, ids: string[]) {
    await UsersService.setMyJurisdictions({
        headers: bearer(await tokenFor(user)),
        body: { jurisdiction_ids: ids },
    })
}

export function idOf(
    tree: { id: string; name_path: string }[],
    namePath: string,
) {
    const j = tree.find((j) => j.name_path === namePath)
    if (!j) throw new Error(`No jurisdiction at ${namePath}`)
    return j.id
}

// The grid only renders rows near the viewport, so narrow it by search first.
// Matches stay visible under their ancestors.
export async function searchFor(page: Page, term: string) {
    await page.getByRole("textbox", { name: "Search jurisdictions" }).fill(term)
    await expect(page.getByRole("grid").locator("mark").first()).toBeVisible()
}

// A single jurisdiction's switch; subtree switches start "Enable all of"
export function switchFor(page: Page, label: string): Locator {
    return page
        .getByRole("grid")
        .getByRole("switch", { name: label, exact: true })
}

export function subtreeSwitchFor(
    page: Page,
    name: string,
    scope: string,
): Locator {
    return page.getByRole("grid").getByRole("switch", {
        name: new RegExp(`^Enable all of ${name} ${scope} \\(`),
    })
}

export async function waitForGrid(page: Page) {
    await expect(
        page.getByRole("grid").getByRole("switch").first(),
    ).toBeVisible()
}
