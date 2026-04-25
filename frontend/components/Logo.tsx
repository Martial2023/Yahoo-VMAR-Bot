import { Code, Group, Component } from 'lucide-react'
import React from 'react'
import Image from 'next/image'

export default function Logo() {
    return (
        <div className={"flex items-center space-x-1"}>
            {/* <div className="bg-orange-500 rounded-lg p-2">
                <Component className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold">BBros</span> */}
            <Code />
            <h2 className="text-2xl font-bold flex items-center">
                Nullify
            </h2>
        </div>
    )
}