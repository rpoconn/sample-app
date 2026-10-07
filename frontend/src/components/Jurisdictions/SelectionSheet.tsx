import { Check, Copy, ListChecks } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import type { SelectionGroup } from "./selectionSummary"
import type { JurisdictionMode } from "./types"

// The current selection in two forms: a readable summary, and the raw ids that
// another system would consume, with the endpoint that returns the same list
export function SelectionSheet({
    open,
    onOpenChange,
    mode,
    ownerId,
    groups,
    ids,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    mode: JurisdictionMode
    // The company's id in company scope, the user's otherwise
    ownerId: string
    groups: SelectionGroup[]
    ids: string[]
}) {
    const [copied, copy] = useCopyToClipboard()
    const json = JSON.stringify(
        {
            scope: mode,
            [mode === "company" ? "company_id" : "user_id"]: ownerId,
            jurisdiction_ids: ids,
            count: ids.length,
        },
        null,
        4,
    )
    const endpoint =
        mode === "company"
            ? `GET /api/v1/companies/${ownerId}/jurisdictions/ids`
            : "GET /api/v1/users/me/jurisdictions/ids"

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="w-full sm:max-w-md">
                <SheetHeader className="pb-0">
                    <SheetTitle className="flex items-center gap-2">
                        <ListChecks className="size-5" />
                        {mode === "company"
                            ? "Company selection"
                            : "Your selection"}
                    </SheetTitle>
                    <SheetDescription>
                        {ids.length === 0
                            ? "No jurisdictions are on."
                            : `${ids.length} jurisdiction${ids.length === 1 ? "" : "s"} on${mode === "company" ? " for this company" : ", monitored for you"}.`}
                    </SheetDescription>
                </SheetHeader>
                <Tabs
                    defaultValue="summary"
                    className="min-h-0 flex-1 px-4 pb-4"
                >
                    <TabsList className="w-full">
                        <TabsTrigger value="summary">Summary</TabsTrigger>
                        <TabsTrigger value="ids">IDs (JSON)</TabsTrigger>
                    </TabsList>
                    <TabsContent
                        value="summary"
                        className="min-h-0 overflow-y-auto"
                    >
                        {groups.length === 0 ? (
                            <p className="py-8 text-center text-sm text-muted-foreground">
                                Nothing selected yet. Turn on jurisdictions in
                                the table to see them here.
                            </p>
                        ) : (
                            <dl className="flex flex-col gap-4 py-2">
                                {groups.map((group) => (
                                    <div
                                        key={group.parent?.id ?? "top"}
                                        className="flex flex-col gap-1.5"
                                    >
                                        <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                            {group.parent?.name_path ??
                                                "Top level"}
                                        </dt>
                                        {group.entries.map(
                                            ({
                                                jurisdiction: j,
                                                flagUrl,
                                                allOf,
                                            }) => (
                                                <dd
                                                    key={j.id}
                                                    className="m-0 flex items-center gap-2 text-sm"
                                                >
                                                    {flagUrl ? (
                                                        <img
                                                            src={flagUrl}
                                                            alt=""
                                                            className="h-3.5 w-5 shrink-0 rounded-[2px] border object-cover"
                                                        />
                                                    ) : (
                                                        <span className="w-5 shrink-0" />
                                                    )}
                                                    <span className="truncate">
                                                        {j.name}
                                                    </span>
                                                    {j.code && (
                                                        <span className="text-xs text-muted-foreground">
                                                            {j.code}
                                                        </span>
                                                    )}
                                                    {allOf != null && (
                                                        <span className="ml-auto shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                                                            All {allOf}
                                                        </span>
                                                    )}
                                                </dd>
                                            ),
                                        )}
                                    </div>
                                ))}
                            </dl>
                        )}
                    </TabsContent>
                    <TabsContent
                        value="ids"
                        className="flex min-h-0 flex-col gap-3"
                    >
                        <div className="flex items-center justify-between gap-2">
                            <code className="truncate text-xs text-muted-foreground">
                                {endpoint}
                            </code>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => copy(json)}
                            >
                                {copied === json ? <Check /> : <Copy />}
                                {copied === json ? "Copied" : "Copy JSON"}
                            </Button>
                        </div>
                        <pre
                            data-testid="selection-json"
                            className="min-h-0 flex-1 overflow-auto rounded-md border bg-muted p-3 font-mono text-xs"
                        >
                            {json}
                        </pre>
                    </TabsContent>
                </Tabs>
            </SheetContent>
        </Sheet>
    )
}

export default SelectionSheet
