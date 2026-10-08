import { useMutation } from "@tanstack/react-query"

import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { JurisdictionGridService } from "./JurisdictionGridService"
import type { JurisdictionMode } from "./types"

export type SubtreeChange = { rootId: string; enabled: boolean }

// Turns a jurisdiction and everything selectable under it on or off in this scope
export function useSelectionMutation(
    mode: JurisdictionMode,
    companyId: string,
    onSettled: () => void,
) {
    const { showErrorToast } = useCustomToast()

    return useMutation({
        mutationFn: ({ rootId, enabled }: SubtreeChange) =>
            JurisdictionGridService.saveSubtree(
                mode,
                companyId,
                rootId,
                enabled,
            ),
        onError: (err) => handleError.call(showErrorToast, err),
        onSettled,
    })
}

export default useSelectionMutation
