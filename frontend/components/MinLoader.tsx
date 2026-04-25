import { Trefoil } from 'ldrs/react'
import 'ldrs/react/Trefoil.css'

const MinLoader = () => {
    return (
        <div>
            <div className='dark:hidden'>
                <Trefoil
                    size="46"
                    stroke="4"
                    speed="1.4"
                    color="black"
                />
            </div>
            <div className='hidden dark:block'>
                <Trefoil
                    size="46"
                    stroke="4"
                    speed="1.4"
                    color="white"
                />
            </div>
        </div>

    )
}

export default MinLoader