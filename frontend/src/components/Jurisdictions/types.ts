import type { JurisdictionPublic } from "@/client"

export type JurisdictionMode = "company" | "user"

export type JurisdictionRow = {
    jurisdiction: JurisdictionPublic
    expanded: boolean
    checked: boolean
    disabled: boolean
    disabledReason?: string
}

export type JurisdictionGridContext = {
    toggleExpanded: (id: string) => void
    toggleEnabled: (id: string, enabled: boolean) => void
}
