import { Building2, Lock, User } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import type { JurisdictionMode } from "./types"

// Shared with the grid frame so the scope stays visible while scrolling
export const scopeAccent: Record<JurisdictionMode, string> = {
    company: "border-l-4 border-l-amber-500",
    user: "border-l-4 border-l-sky-500",
}

export function ScopeBanner({
    mode,
    canEditCompany,
    lockedCount,
}: {
    mode: JurisdictionMode
    canEditCompany: boolean
    lockedCount: number
}) {
    const Icon = mode === "user" ? User : canEditCompany ? Building2 : Lock
    return (
        <Alert
            role="status"
            className={cn(
                scopeAccent[mode],
                mode === "company"
                    ? "bg-amber-50 dark:bg-amber-950/30"
                    : "bg-sky-50 dark:bg-sky-950/30",
            )}
        >
            <Icon />
            <AlertTitle>
                {mode === "user"
                    ? "These are your personal jurisdictions"
                    : canEditCompany
                      ? "You're editing jurisdictions licenses for this company"
                      : "Viewing your company's jurisdictions"}
            </AlertTitle>
            <AlertDescription>
                {mode === "user" ? (
                    <p>
                        Choose the jurisdictions where you want compliance
                        checks.
                        {lockedCount > 0 && (
                            <span className="text-muted-foreground">
                                {" "}
                                To add more jurisdictions company-wide, speak
                                with your{" "}
                                <a
                                    href="mailto:sales@daptic.com"
                                    className="underline underline-offset-4 hover:text-foreground"
                                >
                                    Daptic
                                </a>{" "}
                                sales associate.
                            </span>
                        )}
                    </p>
                ) : canEditCompany ? (
                    <p>
                        Changes apply to every user of this company. Turning a
                        jurisdiction off also removes it from anyone who
                        selected it.
                    </p>
                ) : (
                    <p>
                        Only company admins can change these. Users of this
                        company can choose from the enabled ones.
                    </p>
                )}
            </AlertDescription>
        </Alert>
    )
}

export default ScopeBanner
