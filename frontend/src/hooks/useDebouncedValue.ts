import { useEffect, useState } from "react"

// Follows `value` after it has settled for `delay` ms. Changes `immediate`
// approves skip the wait.
export function useDebouncedValue<T>(
    value: T,
    delay: number,
    immediate?: (prev: T, next: T) => boolean,
) {
    const [debounced, setDebounced] = useState(value)

    useEffect(() => {
        if (Object.is(value, debounced)) return
        if (immediate?.(debounced, value)) {
            setDebounced(value)
            return
        }
        const timer = setTimeout(() => setDebounced(value), delay)
        return () => clearTimeout(timer)
    }, [value, debounced, delay, immediate])

    return debounced
}
