import { Button } from '@/components/ui/button'
import { ArrowLeft, TrendingUp } from 'lucide-react'
import Link from 'next/link'
import React from 'react'
import { ThemeToggle } from '@/components/ThemeToggle'
// import { Spotlight } from '@/components/ui/spotlight-new'

type Props = {
    children: React.ReactNode
}

const layout = ({ children }: Props) => {
    return (
        <main className=' relative w-full min-h-screen overflow-hidden py-12'>
            {/* <Spotlight /> */}
            {/* <ScrollProgress className="top-0 h-1 z-[1000]" /> */}
            <div className='p-3 md:p-8 md:px-[8%] text-xl flex items-center justify-between'>
                <Link
                    href={"/"}
                    className='flex items-center rounded-full'
                >
                    <Button
                        className='rounded-full text-sm'
                        variant={"outline"}
                    >
                        <ArrowLeft />
                        Retour
                    </Button>
                </Link>

                <ThemeToggle />
            </div>

            <div className='flex flex-col items-center justify-center'>
                <div className='w-full flex items-center justify-center mb-1'>
                    <h2 className="text-2xl font-bold flex items-center gap-1">
                        <TrendingUp className='size-5 text-primary dark:text-white' />
                        <span className="text-primary dark:text-white">VMAR Bot</span>
                    </h2>
                </div>

                {children}
            </div>
        </main>
    )
}

export default layout