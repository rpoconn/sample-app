import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { AxiosError } from "axios"

import {
    type Body_login_login_access_token as AccessToken,
    LoginService,
    type UserPublic,
    type UserRegister,
    UsersService,
} from "@/client"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
    return localStorage.getItem("access_token") !== null
}

// The token is invalid (expired, revoked, or its user is gone) or the account is disabled
const isAuthError = (error: unknown) => {
    if (!(error instanceof AxiosError)) {
        return false
    }
    const status = error.response?.status
    const code = error.response?.data?.code
    return (
        status === 401 ||
        (status === 403 &&
            (code === "user_inactive" || code === "company_inactive"))
    )
}

const useAuth = () => {
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const { showErrorToast } = useCustomToast()

    const { data: user } = useQuery<UserPublic | null, Error>({
        queryKey: ["currentUser"],
        queryFn: async () => (await UsersService.readUserMe()).data,
        enabled: isLoggedIn(),
    })

    const signUpMutation = useMutation({
        mutationFn: (data: UserRegister) =>
            UsersService.registerUser({ body: data }),
        onSuccess: () => {
            navigate({ to: "/login" })
        },
        onError: handleError.bind(showErrorToast),
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: ["users"] })
        },
    })

    const login = async (data: AccessToken) => {
        const response = await LoginService.loginAccessToken({
            body: data,
        })
        localStorage.setItem("access_token", response.data.access_token)
    }

    const loginMutation = useMutation({
        mutationFn: login,
        onSuccess: () => {
            navigate({ to: "/" })
        },
        onError: handleError.bind(showErrorToast),
    })

    const logout = async () => {
        try {
            // Revoke the token server-side; log out locally even if this fails
            await LoginService.logout()
        } catch {}
        localStorage.removeItem("access_token")
        // Drop cached data so the next user doesn't see the previous user's
        queryClient.clear()
        navigate({ to: "/login" })
    }

    return {
        signUpMutation,
        loginMutation,
        logout,
        user,
    }
}

export { isAuthError, isLoggedIn }
export default useAuth
