import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../test/helpers'
import PageHeading from './PageHeading'

describe('page heading', () => {
  it('shows the title and keeps the description behind an info button for phones', async () => {
    renderApp(<PageHeading title="Orçamentos">Planeje quanto gastar.</PageHeading>)

    expect(screen.getByRole('heading', { name: 'Orçamentos' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sobre Orçamentos' }))

    expect((await screen.findAllByText('Planeje quanto gastar.')).length).toBeGreaterThan(0)
  })

  it('has no info button when there is no description', () => {
    renderApp(<PageHeading title="Orçamentos" />)

    expect(screen.queryByRole('button', { name: /sobre/i })).not.toBeInTheDocument()
  })
})
