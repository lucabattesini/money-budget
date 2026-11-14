import { useState } from 'react'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderApp } from '../test/helpers'
import CategoryPicker from './CategoryPicker'

const CATEGORIES = [
  { id: 1, name: '🛒 Supermercado', group_id: 'g1', group_name: 'Alimentação', group_position: 1 },
  { id: 2, name: '☕ Café', group_id: 'g1', group_name: 'Alimentação', group_position: 1 },
  { id: 3, name: '🏠 Aluguel', group_id: 'g2', group_name: 'Moradia', group_position: 2 },
  { id: 4, name: 'Água', group_id: 'g2', group_name: 'Moradia', group_position: 2 },
  { id: 5, name: 'Sem categoria', group_id: 'g3', group_name: 'Outros', group_position: 9 },
]

function Harness({ onChange = () => {}, start = '', ...props }) {
  const [value, setValue] = useState(start)
  return (
    <CategoryPicker
      categories={props.categories ?? CATEGORIES}
      value={value}
      onChange={(next) => { setValue(next); onChange(next) }}
      aria-label="Categoria"
      {...props}
    />
  )
}

const box = () => screen.getByRole('combobox', { name: 'Categoria' })
const open = async () => userEvent.click(box())
const optionNames = () => screen.queryAllByRole('option').map((option) => option.textContent)

describe('category picker', () => {
  it('lists the categories under their groups, groups in their own order and categories A-Z inside', async () => {
    renderApp(<Harness />)

    await open()

    expect(await screen.findAllByRole('option')).toHaveLength(5)
    const headings = screen.getAllByText(/^(Alimentação|Moradia|Outros)$/).map((heading) => heading.textContent)
    expect(headings).toEqual(['Alimentação', 'Moradia', 'Outros'])
    expect(optionNames()).toEqual(['☕ Café', '🛒 Supermercado', 'Água', '🏠 Aluguel', 'Sem categoria']) // A-Z by the words, emoji ignored
  })

  it('narrows the list while typing, ignoring accents, capitals and the emoji, and hides groups with no match', async () => {
    renderApp(<Harness />)

    await userEvent.type(box(), 'CAFE')

    expect(await screen.findByRole('option', { name: '☕ Café' })).toBeInTheDocument()
    expect(optionNames()).toEqual(['☕ Café'])
    expect(screen.queryByText('Moradia')).not.toBeInTheDocument()
  })

  it('keeps every key typed with no pause between them', async () => {
    renderApp(<Harness />)

    await userEvent.type(box(), 'supermercado')

    expect(box()).toHaveValue('supermercado')
  })

  it('says so when nothing matches', async () => {
    renderApp(<Harness />)

    await userEvent.type(box(), 'zzz')

    expect(await screen.findByText('Nenhuma categoria encontrada')).toBeInTheDocument()
  })

  it('chooses with the keyboard: arrows, Enter, and Escape closes without choosing', async () => {
    const onChange = vi.fn()
    renderApp(<Harness onChange={onChange} />)

    await userEvent.type(box(), 'alu')
    await userEvent.keyboard('{ArrowDown}{Enter}')

    expect(onChange).toHaveBeenCalledWith('3')
    expect(box()).toHaveValue('🏠 Aluguel')

    await userEvent.click(box())
    // The list opens a moment after the click. Escape pressed before it is open would be ignored and the list would open
    // after it (seen on slow CI machines), so wait until it is open.
    await screen.findAllByRole('option')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryAllByRole('option')).toHaveLength(0)) // the list closes
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('shows the whole list again when opened after a choice', async () => {
    renderApp(<Harness start="2" />)
    expect(box()).toHaveValue('☕ Café')

    await open()

    expect(await screen.findAllByRole('option')).toHaveLength(5)
  })

  it('can offer "no category" as a first choice, and choosing it gives an empty value', async () => {
    const onChange = vi.fn()
    renderApp(<Harness onChange={onChange} start="1" emptyLabel="Todas" />)

    await open()
    const list = await screen.findAllByRole('option')
    expect(list[0]).toHaveTextContent('Todas')
    await userEvent.click(list[0])

    expect(onChange).toHaveBeenCalledWith('')
    expect(box()).toHaveValue('Todas')
  })

  it('can offer extra first choices', async () => {
    const onChange = vi.fn()
    renderApp(<Harness onChange={onChange} extra={[{ value: 'new', label: 'Criar uma categoria nova' }]} />)

    await open()
    await userEvent.click(await screen.findByRole('option', { name: 'Criar uma categoria nova' }))

    expect(onChange).toHaveBeenCalledWith('new')
  })

  it('lists categories without any group data as one plain A-Z list', async () => {
    renderApp(<Harness categories={[{ id: 1, name: 'Zebra' }, { id: 2, name: 'Abelha' }]} />)

    await open()

    expect((await screen.findAllByRole('option')).map((option) => option.textContent)).toEqual(['Abelha', 'Zebra'])
  })

  it('does not open when disabled', async () => {
    renderApp(<Harness disabled />)

    await open()

    expect(screen.queryAllByRole('option')).toHaveLength(0)
    expect(within(document.body).getByRole('combobox', { name: 'Categoria' })).toBeDisabled()
  })
})
