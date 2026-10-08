import type { JurisdictionPublic } from "@/client"

// region-flags names its SVGs by ISO code: "US.svg", "US-WA.svg", "CA-BC.svg".
// Each becomes a hashed asset URL, so a flag is only downloaded when it is shown.
const flagUrls: Record<string, string> = Object.fromEntries(
    Object.entries(
        import.meta.glob<string>("@region-flags/svg/*.svg", {
            eager: true,
            query: "?url",
            import: "default",
        }),
    ).map(([file, url]) => [
        file.slice(file.lastIndexOf("/") + 1, -".svg".length),
        url,
    ]),
)

// Subdivisions whose flag is filed under their ISO 3166-1 code instead
const aliases: Record<string, string> = { "US-PR": "PR" }

type ById = Map<string, JurisdictionPublic>

function nearestCountryCode(j: JurisdictionPublic, byId: ById) {
    for (
        let a = j.parent_id ? byId.get(j.parent_id) : undefined;
        a;
        a = a.parent_id ? byId.get(a.parent_id) : undefined
    ) {
        if (a.region_type === "country") return a.code ?? undefined
    }
}

function ownFlagUrl(j: JurisdictionPublic, byId: ById) {
    if (!j.code) return undefined
    let key: string | undefined
    if (j.region_type === "country") key = j.code
    else if (j.region_type === "subdivision") {
        const country = nearestCountryCode(j, byId)
        if (country) key = `${country}-${j.code}`
    }
    return key ? flagUrls[aliases[key] ?? key] : undefined
}

// Structural groupings get no flag. Other rows without a flag of their own (e.g.
// "National", or a city) show their nearest ancestor's flag.
export function flagUrlFor(j: JurisdictionPublic, byId: ById) {
    if (j.is_structural && !j.region_type) return undefined
    for (
        let a: JurisdictionPublic | undefined = j;
        a;
        a = a.parent_id ? byId.get(a.parent_id) : undefined
    ) {
        const url = ownFlagUrl(a, byId)
        if (url) return url
    }
}

// The first of the server's flag keys (nearest first) there is an SVG for
export function flagUrlForKeys(keys: string[]) {
    for (const key of keys) {
        const url = flagUrls[aliases[key] ?? key]
        if (url) return url
    }
}

// Held so the browser keeps the decoded bitmaps; rows mounting during scroll or
// expand then paint their flag on the first frame instead of popping in.
const preloaded = new Map<string, HTMLImageElement>()

export function preloadFlags(urls: Iterable<string | undefined>) {
    for (const url of urls) {
        if (!url || preloaded.has(url)) continue
        const img = new Image()
        img.src = url
        img.decode().catch(() => preloaded.delete(url))
        preloaded.set(url, img)
    }
}
