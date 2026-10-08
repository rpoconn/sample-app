import { Check, Minus } from "lucide-react"

import { cn } from "@/lib/utils"

export type SwitchState = "on" | "mixed" | "off"

// The knob of TriStateSwitch: a check when on, a dash when partly on, blank when off
export function SwitchThumb({ state }: { state: SwitchState }) {
    const Glyph = state === "on" ? Check : state === "mixed" ? Minus : null
    return (
        <span
            className={cn(
                "flex size-4 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/10 transition-colors",
                state !== "off" && "text-primary",
            )}
        >
            {Glyph && <Glyph className="size-3" strokeWidth={3.5} />}
        </span>
    )
}

export default SwitchThumb
