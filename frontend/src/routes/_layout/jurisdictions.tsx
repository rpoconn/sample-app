import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { JurisdictionGrid } from "@/components/jurisdictions/JurisdictionGrid"
import { Skeleton } from "@/components/ui/Skeleton"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/jurisdictions")({
    component: Jurisdictions,
    head: () => ({
        meta: [
            {
                title: "Jurisdictions - Daptic",
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

    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">
                    Jurisdictions
                </h1>
                <p className="text-muted-foreground">
                    Choose the jurisdictions you personally manage
                </p>
            </div>
            {user ? (
                <Suspense fallback={<PendingJurisdictions />}>
                    <JurisdictionGrid mode="user" user={user} />
                </Suspense>
            ) : (
                <PendingJurisdictions />
            )}
        </div>
    )
}
