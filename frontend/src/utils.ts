import { AxiosError } from "axios"

function extractErrorMessage(err: Error): string {
    if (err instanceof AxiosError) {
        const errDetail = (err.response?.data as any)?.detail
        if (typeof errDetail === "string") {
            return errDetail
        }
        return err.message
    }
    return "Something went wrong."
}

export const handleError = function (this: (msg: string) => void, err: Error) {
    const errorMessage = extractErrorMessage(err)
    this(errorMessage)
}

export const getInitials = (name: string): string => {
    return name
        .split(" ")
        .slice(0, 2)
        .map((word) => word[0])
        .join("")
        .toUpperCase()
}
