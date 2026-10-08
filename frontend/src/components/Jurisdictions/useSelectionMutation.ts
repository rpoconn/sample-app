import { useMutation } from "@tanstack/react-query"
import { AxiosError } from "axios"

import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { JurisdictionGridService } from "./JurisdictionGridService"
import type { JurisdictionMode } from "./types"

export type SubtreeChange = {
    rootId: string
    enabled: boolean
    // Whether the click was on the row's select-all switch
    subtree: boolean
    // The previewed version a confirmed change commits against; plain toggles
    // send none
    version?: number
}

// Turns a jurisdiction and everything selectable under it on or off in this scope.
// A change made against a version that has since moved on goes to onConflict.
export function useSelectionMutation(
    mode: JurisdictionMode,
    companyId: string,
    onSettled: () => void,
    onConflict: (change: SubtreeChange) => void,
) {
    const { showErrorToast } = useCustomToast()

    return useMutation({
        mutationFn: ({ rootId, enabled, version }: SubtreeChange) =>
            JurisdictionGridService.saveSubtree(
                mode,
                companyId,
                rootId,
                enabled,
                version,
            ),
        onError: (err, change) => {
            if (err instanceof AxiosError && err.response?.status === 412) {
                showErrorToast(
                    "The license changed while you were reviewing. Showing the latest.",
                )
                onConflict(change)
                return
            }
            handleError.call(showErrorToast, err)
        },
        onSettled,
    })
}

export default useSelectionMutation
