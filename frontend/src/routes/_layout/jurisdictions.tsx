import ToggleButton from "@mui/material/ToggleButton"
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import {
    JurisdictionGrid,
    type JurisdictionMode,
} from "@/components/Jurisdictions/JurisdictionGrid"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/jurisdictions")({
    component: Jurisdictions,
    head: () => ({
        meta: [
            {
                title: "Jurisdictions - FastAPI Template",
            },
        ],
    }),
})

function PendingJurisdictions() {
    return (
        <div className="flex flex-col gap-2">
            {["a", "b", "c", "d", "e", "f", "g", "h"].map((key) => (
                <Skeleton key={key} className="h-8 w-full" />
            ))}
        </div>
    )
}

function Jurisdictions() {
    const { user } = useAuth()
    const [mode, setMode] = useState<JurisdictionMode>("user")

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">
                        Jurisdictions
                    </h1>
                    <p className="text-muted-foreground">
                        Choose the jurisdictions you work in
                    </p>
                </div>
                <ToggleButtonGroup
                    exclusive
                    size="small"
                    color="primary"
                    value={mode}
                    onChange={(_, value: JurisdictionMode | null) => {
                        if (value) setMode(value)
                    }}
                    aria-label="Jurisdiction view"
                >
                    <ToggleButton value="company">Company</ToggleButton>
                    <ToggleButton value="user">User</ToggleButton>
                </ToggleButtonGroup>
            </div>
            {user ? (
                <Suspense fallback={<PendingJurisdictions />}>
                    <JurisdictionGrid mode={mode} user={user} />
                </Suspense>
            ) : (
                <PendingJurisdictions />
            )}
        </div>
    )
}
