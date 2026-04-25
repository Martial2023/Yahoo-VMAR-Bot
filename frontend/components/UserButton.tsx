"use client";

import {
    ChartPie,
    LogOut,
} from "lucide-react";

import {
    Avatar,
    AvatarFallback,
    AvatarImage,
} from "@/components/ui/avatar";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCurrentUser } from "@/lib/useCurrentUser";
import { ThemeToggle } from "./ThemeToggle";
import { signOut } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import Link from "next/link";

export function UserButton() {
    const isMobile = true;
    const user = useCurrentUser() as { role?: string; id: string; createdAt: Date; updatedAt: Date; email: string; emailVerified: boolean; name: string; image?: string | null | undefined; } | null;
    const router = useRouter();
    const handleSignOut = async () => {
        await signOut({
            fetchOptions: {
                onSuccess: () => {
                    router.push("/sign-in")
                }
            }
        });
    };


    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <button className="focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-zinc-300 dark:focus-visible:ring-zinc-700 rounded-full transition-all hover:opacity-80 cursor-pointer">
                    <Avatar className="h-9 w-9 border-2 border-zinc-200 dark:border-zinc-800">
                        <AvatarImage
                            src={user?.image || ""}
                            alt={user?.name || "user"}
                        />
                        <AvatarFallback className="font-semibold">
                            {user?.name?.charAt(0).toUpperCase()}
                        </AvatarFallback>
                    </Avatar>
                </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
                className="w-60 rounded-xl border-zinc-200 dark:border-zinc-800 shadow-lg"
                side={isMobile ? "bottom" : "right"}
                align="end"
                sideOffset={8}
            >
                {user && (
                    <DropdownMenuLabel className="pb-2">
                        <div className="flex items-center gap-3">
                            <Avatar className="h-10 w-10 border-2 border-zinc-200 dark:border-zinc-800">
                                <AvatarImage src={user.image || ""} alt={user.name || "user"} />
                                <AvatarFallback className="font-semibold">
                                    {user.name?.charAt(0).toUpperCase()}
                                </AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col space-y-0.5 overflow-hidden">
                                <p className="text-sm font-semibold text-zinc-900 dark:text-white truncate">
                                    {user.name}
                                </p>
                                <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate">
                                    {user.email}
                                </p>
                            </div>
                        </div>
                    </DropdownMenuLabel>
                )}

                <DropdownMenuSeparator />

                <DropdownMenuGroup className="hidden md:block">
                    <DropdownMenuItem className="cursor-pointer">
                        <ThemeToggle />
                    </DropdownMenuItem>
                </DropdownMenuGroup>

                <DropdownMenuSeparator className="hidden md:block" />

                <DropdownMenuItem className="cursor-pointer" asChild>
                    <Link href="/admin/dashboard" className="flex items-center">
                        <ChartPie className="mr-2 h-4 w-4" />
                        <span>Dashboard</span>
                    </Link>
                </DropdownMenuItem>

                <DropdownMenuItem
                    className="hidden md:flex cursor-pointer text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400 focus:bg-red-50 dark:focus:bg-red-950/30"
                    onClick={handleSignOut}
                >
                    <LogOut className="mr-2 h-4 w-4" />
                    <span>Sign Out</span>
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
