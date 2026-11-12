import { useState } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useNavigate } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../test/helpers'
import useBackClosesOverlay from './useBackClosesOverlay'

function Panel({ canClose = true }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  useBackClosesOverlay(open, () => {
    if (!canClose) return false
    setOpen(false)
  })
  return (
    <div>
      <button onClick={() => setOpen(true)}>open</button>
      <button onClick={() => setOpen(false)}>close</button>
      <button onClick={() => navigate(-1)}>back</button>
      {open && <p>panel</p>}
    </div>
  )
}

describe('back closes a panel', () => {
  it('closes the panel when the person goes back, and stays on the page', async () => {
    renderApp(<Panel />, { route: '/budgets' })
    await userEvent.click(screen.getByText('open'))
    expect(screen.getByText('panel')).toBeInTheDocument()

    await userEvent.click(screen.getByText('back'))

    expect(screen.queryByText('panel')).not.toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/budgets')
  })

  it('removes its history entry when closed by hand, so back leaves the page instead of re-opening', async () => {
    renderApp(<Panel />, { route: '/budgets' })
    await userEvent.click(screen.getByText('open'))
    await userEvent.click(screen.getByText('close'))
    expect(screen.queryByText('panel')).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('back')) // there is nothing before the first page in a memory router
    expect(screen.queryByText('panel')).not.toBeInTheDocument()
  })

  it('keeps the panel open when it refuses to close, and back works again afterwards', async () => {
    renderApp(<Panel canClose={false} />, { route: '/budgets' })
    await userEvent.click(screen.getByText('open'))

    await userEvent.click(screen.getByText('back'))

    expect(screen.getByText('panel')).toBeInTheDocument()
  })
})
