import { useMutation, useQueryClient } from "@tanstack/react-query"

import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

// Saves a list of selected ids, updating the cached list optimistically
export function useSelectionMutation(
    queryKey: string[],
    save: (ids: string[]) => Promise<unknown>,
    onSaved?: () => void,
) {
    const queryClient = useQueryClient()
    const { showErrorToast } = useCustomToast()

    return useMutation({
        mutationFn: save,
        onMutate: async (ids) => {
            await queryClient.cancelQueries({ queryKey })
            const previous = queryClient.getQueryData<string[]>(queryKey)
            queryClient.setQueryData(queryKey, ids)
            return { previous }
        },
        onError: (err, _ids, ctx) => {
            queryClient.setQueryData(queryKey, ctx?.previous)
            handleError.call(showErrorToast, err)
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey })
            onSaved?.()
        },
    })
}

export default useSelectionMutation
