import { useState } from "react"

import type { JurisdictionAffectedUser } from "@/client"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export type PendingDisable = {
    // The row whose switch was clicked; everything under it goes when subtree
    rootId: string
    subtree: boolean
    name: string
    // Each user who'd lose at least one of the ids, once
    users: JurisdictionAffectedUser[]
}

// Past this many users the list gets a search box
const searchThreshold = 8

export function ConfirmDisableDialog({
    open,
    pending,
    companyName,
    onCancel,
    onConfirm,
}: {
    open: boolean
    // Kept after closing so the text doesn't blank out while animating away
    pending: PendingDisable | null
    companyName: string
    onCancel: () => void
    onConfirm: (pending: PendingDisable) => void
}) {
    const [query, setQuery] = useState("")
    const subtree = pending?.subtree ?? false
    const all = pending?.users ?? []
    const count = all.length
    const users = count === 1 ? "1 user" : `${count.toLocaleString()} users`
    const q = query.trim().toLowerCase()
    const shown = q
        ? all.filter(
              (u) =>
                  u.email.toLowerCase().includes(q) ||
                  u.full_name?.toLowerCase().includes(q),
          )
        : all
    return (
        <Dialog open={open} onOpenChange={(open) => !open && onCancel()}>
            <DialogContent
                // Default focus on Cancel so Enter doesn't confirm by accident
                onOpenAutoFocus={(e) => {
                    e.preventDefault()
                    setQuery("")
                    document
                        .querySelector<HTMLButtonElement>(
                            "[data-confirm-cancel]",
                        )
                        ?.focus()
                }}
            >
                <DialogHeader>
                    <DialogTitle>
                        Turn off {pending?.name}
                        {subtree && " and everything under it"} for all of{" "}
                        {companyName}?
                    </DialogTitle>
                    <DialogDescription>
                        <strong className="text-foreground">{users}</strong>{" "}
                        {count === 1 ? "has" : "have"}{" "}
                        {subtree
                            ? `jurisdictions in ${pending?.name}`
                            : pending?.name}{" "}
                        selected. They'll lose {subtree ? "them" : "it"}, and
                        can't choose {subtree ? "them" : "it"} again until{" "}
                        {subtree ? "they're" : "it's"} turned back on here.
                    </DialogDescription>
                </DialogHeader>
                <div className="flex min-w-0 flex-col gap-2">
                    {count > searchThreshold && (
                        <Input
                            type="search"
                            placeholder={`Search ${users}`}
                            aria-label="Search affected users"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    )}
                    <ul
                        aria-label="Affected users"
                        className="max-h-[min(18rem,40vh)] divide-y overflow-y-auto rounded-md border"
                    >
                        {shown.map((u) => (
                            <li
                                key={u.id}
                                // Lets the browser skip offscreen rows in very long lists
                                className="flex items-center gap-3 px-3 py-2 text-sm [contain-intrinsic-size:auto_3rem] [content-visibility:auto]"
                            >
                                <div className="min-w-0 flex-1">
                                    <div className="truncate font-medium">
                                        {u.full_name || u.email}
                                    </div>
                                    {u.full_name && (
                                        <div className="text-muted-foreground truncate text-xs">
                                            {u.email}
                                        </div>
                                    )}
                                </div>
                                {subtree && (
                                    <span className="text-muted-foreground shrink-0 text-xs">
                                        {u.jurisdiction_count} selected
                                    </span>
                                )}
                            </li>
                        ))}
                        {shown.length === 0 && (
                            <li className="text-muted-foreground px-3 py-6 text-center text-sm">
                                No users match "{query.trim()}"
                            </li>
                        )}
                    </ul>
                    {q && shown.length > 0 && (
                        <p className="text-muted-foreground text-xs">
                            Showing {shown.length.toLocaleString()} of{" "}
                            {count.toLocaleString()}
                        </p>
                    )}
                </div>
                <DialogFooter>
                    <Button
                        variant="outline"
                        data-confirm-cancel
                        onClick={onCancel}
                    >
                        Cancel
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={() => pending && onConfirm(pending)}
                    >
                        Turn off for everyone
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default ConfirmDisableDialog
