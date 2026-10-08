import { Link } from "@tanstack/react-router"

import { useTheme } from "@/components/ThemeProvider"
import { cn } from "@/lib/utils"
import icon from "/assets/images/dapticIcon.svg"
import iconLight from "/assets/images/dapticIconLight.svg"
import logo from "/assets/images/dapticLogo.svg"
import logoLight from "/assets/images/dapticLogoLight.svg"

interface LogoProps {
    variant?: "full" | "icon" | "responsive"
    className?: string
    asLink?: boolean
}

export function Logo({
    variant = "full",
    className,
    asLink = true,
}: LogoProps) {
    const { resolvedTheme } = useTheme()
    const isDark = resolvedTheme === "dark"

    const fullLogo = isDark ? logoLight : logo
    const iconLogo = isDark ? iconLight : icon

    const content =
        variant === "responsive" ? (
            <>
                <img
                    src={fullLogo}
                    alt="Daptic"
                    className={cn(
                        "h-6 w-auto group-data-[collapsible=icon]:hidden",
                        className,
                    )}
                />
                <img
                    src={iconLogo}
                    alt="Daptic"
                    className={cn(
                        "size-5 hidden group-data-[collapsible=icon]:block",
                        className,
                    )}
                />
            </>
        ) : (
            <img
                src={variant === "full" ? fullLogo : iconLogo}
                alt="Daptic"
                className={cn(
                    variant === "full" ? "h-6 w-auto" : "size-5",
                    className,
                )}
            />
        )

    if (!asLink) {
        return content
    }

    return <Link to="/">{content}</Link>
}
