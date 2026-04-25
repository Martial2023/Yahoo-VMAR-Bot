'use client'
import { deleteProject } from '@/app/(actions)/project'
import { Credenza, CredenzaClose, CredenzaContent, CredenzaDescription, CredenzaFooter, CredenzaHeader, CredenzaTitle, CredenzaTrigger } from '@/components/Credenza'
import Logo from '@/components/Logo'
import { Button } from '@/components/ui/button'
import type { ProjectPreview } from '@/types'
import { Loader2 } from 'lucide-react'
import React from 'react'
import { useState } from 'react'
import { toast } from 'sonner'

type Props = {
    children: React.ReactNode
    deletingProjectIds: string[]
    setProjects: React.Dispatch<React.SetStateAction<ProjectPreview[]>>
    setDeletingProjectIds: React.Dispatch<React.SetStateAction<string[]>>
    projectId: string,
    projectName: string
}
const DeleteProjectModal = ({
    children,
    deletingProjectIds,
    setProjects,
    setDeletingProjectIds,
    projectId,
    projectName
}: Props) => {
    const [isOpen, setIsOpen] = useState(false)
    const handleDeleteProject = async (id: string) => {
        try {

            setDeletingProjectIds((prev) => [...prev, id])
            await deleteProject({ id })
            setProjects((prev) => prev.filter((project) => project.id !== id))
            toast.success("Project deleted")
            setIsOpen(false)
        } catch (error) {
            toast.error("Failed to delete project")
        } finally {
            setDeletingProjectIds((prev) => prev.filter((projectId) => projectId !== id))
        }
    }
    return (
        <Credenza open={isOpen} onOpenChange={setIsOpen}>
            <CredenzaTrigger asChild>
                {children}
            </CredenzaTrigger>

            <CredenzaContent className="border-none shadow-xl dark:bg-zinc-900 mx-0.5">
                <CredenzaHeader className="pb-2">
                    <CredenzaTitle className="text-3xl font-semibold text-primary flex items-center justify-between">
                        <Logo />
                    </CredenzaTitle>
                    <CredenzaDescription className="text-gray-500 text-sm italic text-center">
                        Supprimer le projet <span className="font-bold">{projectName}</span> ?
                    </CredenzaDescription>
                </CredenzaHeader>

                <CredenzaFooter className='flex flex-row items-center gap-4 w-full pt-2 mx-2'>
                    <CredenzaClose asChild>
                        <Button size={"sm"} variant={"outline"} className='w-1/2'>
                            Annuler
                        </Button>
                    </CredenzaClose>

                    <Button size={"sm"} className='w-1/2' onClick={() => handleDeleteProject(projectId)} disabled={deletingProjectIds.includes(projectId)}>
                        {deletingProjectIds.includes(projectId) ? <Loader2 className='size-3 animate-spin' /> : 'Supprimer'}
                    </Button>
                </CredenzaFooter>
            </CredenzaContent>
        </Credenza>
    )
}

export default DeleteProjectModal