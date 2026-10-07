import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { UsersService } from "@/client"
import { JurisdictionGrid } from "@/components/Jurisdictions/JurisdictionGrid"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/company-admin")({
    component: CompanyAdmin,
    beforeLoad: async () => {
        const { data: user } = await UsersService.readUserMe()
        if (!user.is_superuser && user.company_role !== "admin") {
            throw redirect({
                to: "/",
            })
        }
    },
    head: () => ({
        meta: [
            {
                title: "Company Admin - Daptic",
            },
        ],
    }),
})

function CompanyAdmin() {
    const { user } = useAuth()
    const pending = (
        <div className="flex flex-col gap-2">
            {["a", "b", "c", "d", "e", "f", "g", "h"].map((key) => (
                <Skeleton key={key} className="h-8 w-full" />
            ))}
        </div>
    )

    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">
                    Admin View - changes licensing for a given company
                </h1>
                <p className="text-muted-foreground">
                    Manage which jurisdictions this company operates in
                </p>
            </div>
            {user ? (
                <Suspense fallback={pending}>
                    <JurisdictionGrid mode="company" user={user} />
                </Suspense>
            ) : (
                pending
            )}
        </div>
    )
}
