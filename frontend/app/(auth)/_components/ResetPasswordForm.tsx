'use client'

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import React, { useState } from "react"
import { Loader } from 'lucide-react'
import { authClient } from "@/lib/auth-client"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"

const ResetPasswordForm = ({
    className,
    ...props
}: React.ComponentProps<"div">) => {
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [loading, setLoading] = useState(false)
    const router = useRouter()
    const searchParams = useSearchParams()

    const handleSubmit = async () => {
        if (password !== confirmPassword) {
            toast.error("Les mots de passe ne correspondent pas.")
            return
        }

        if (password.length < 8) {
            toast.error("Le mot de passe doit contenir au moins 8 caractères.")
            return
        }

        const token = searchParams.get("token")
        if (!token) {
            toast.error("Lien de réinitialisation invalide ou expiré.")
            return
        }

        setLoading(true)
        const { error } = await authClient.resetPassword({
            newPassword: password,
            token,
        })
        setLoading(false)

        if (error) {
            toast.error(error.message)
        } else {
            toast.success("Mot de passe réinitialisé avec succès !")
            router.push("/sign-in")
        }
    }

    return (
        <div className={cn("flex flex-col gap-6", className)} {...props}>
            <Card className="overflow-hidden p-0 w-full">
                <CardContent className="p-6 md:p-8">
                    <div className="flex flex-col gap-6">
                        <div className="flex flex-col items-center text-center">
                            <h1 className="text-2xl font-bold">Nouveau mot de passe</h1>
                            <p className="text-balance text-muted-foreground">
                                Choisissez votre nouveau mot de passe
                            </p>
                        </div>

                        <div className="grid gap-2">
                            <Label htmlFor="password">Nouveau mot de passe</Label>
                            <Input
                                id="password"
                                type="password"
                                placeholder="Nouveau mot de passe"
                                onChange={(e) => setPassword(e.target.value)}
                                value={password}
                                required
                                disabled={loading}
                            />
                        </div>

                        <div className="grid gap-2">
                            <Label htmlFor="confirmPassword">Confirmer le mot de passe</Label>
                            <Input
                                id="confirmPassword"
                                type="password"
                                placeholder="Confirmer le mot de passe"
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                value={confirmPassword}
                                required
                                disabled={loading}
                            />
                        </div>

                        <Button
                            type="submit"
                            className="w-full"
                            disabled={loading || !password || !confirmPassword}
                            onClick={handleSubmit}
                        >
                            {loading ? <Loader className="animate-spin" /> : "Réinitialiser le mot de passe"}
                        </Button>

                        <div className="text-center text-sm">
                            <a href="/sign-in" className="underline underline-offset-4">
                                Retour à la connexion
                            </a>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

export default ResetPasswordForm
