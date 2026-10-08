import Tooltip from "@mui/material/Tooltip"
import { CircleOff } from "lucide-react"

import { cn } from "@/lib/utils"

const SUPPORT_EMAIL = "support@daptic.ai"

// Marks a jurisdiction the license doesn't cover, and points to support
export function LockedIcon({ className }: { className?: string }) {
    return (
        <Tooltip
            title={
                <span>
                    Contact{" "}
                    <a
                        href={`mailto:${SUPPORT_EMAIL}`}
                        className="font-medium underline underline-offset-2"
                    >
                        Daptic
                    </a>{" "}
                    to add more jurisdictions to your license.
                </span>
            }
            placement="top"
            enterDelay={150}
            // Time to move onto the tooltip's link
            leaveDelay={200}
            arrow
        >
            <span
                role="img"
                aria-label={`Not enabled for your license. Contact Daptic to add more jurisdictions to your license.`}
                className={cn("flex shrink-0 items-center", className)}
            >
                <CircleOff className="size-3.5 text-muted-foreground" />
            </span>
        </Tooltip>
    )
}

export default LockedIcon
