import { describe, expect, it } from 'vitest'
import { EMOJI_CHOICES, compareCategories, compareNames, groupCategories, joinName, matchesSearch, plainName, searchKey, splitName } from './categoryName'

describe('splitting a category name', () => {
  it.each([
    ['🛒 Supermercado', '🛒', 'Supermercado'],
    ['  🛒   Supermercado ', '🛒', 'Supermercado'],
    ['Supermercado', '', 'Supermercado'],
    ['✈️ Viagem', '✈️', 'Viagem'], // an emoji followed by a variation selector
    ['🏋️ Exercícios e Esportes', '🏋️', 'Exercícios e Esportes'],
    ['🧑‍💻 Trabalho remoto', '🧑‍💻', 'Trabalho remoto'], // emoji joined with a zero-width joiner
    ['👍🏽 Combinado', '👍🏽', 'Combinado'], // with a skin tone
    ['🇧🇷 Brasil', '🇧🇷', 'Brasil'], // a flag
    ['Carro 🚗', '', 'Carro 🚗'], // only an emoji at the start belongs to the name's decoration
    ['1️⃣ Primeiro', '', '1️⃣ Primeiro'], // a digit is a word, not an emoji
    ['€ Euro', '', '€ Euro'],
    ['★ Favorito', '★', 'Favorito'], // the same rule as the server: any leading symbol counts
    ['© Direitos', '©', 'Direitos'],
    ['🛒', '🛒', ''],
    ['', '', ''],
    [null, '', ''],
  ])('%s -> emoji "%s", words "%s"', (name, emoji, text) => {
    expect(splitName(name)).toEqual({ emoji, text })
  })

  it('has the words only as plainName', () => {
    expect(plainName('🛒 Supermercado')).toBe('Supermercado')
  })
})

describe('putting a name together', () => {
  it('puts the emoji, a space and the words together', () => {
    expect(joinName('🌱', 'Plantas')).toBe('🌱 Plantas')
  })

  it('leaves the words alone without an emoji', () => {
    expect(joinName('', 'Plantas')).toBe('Plantas')
  })

  it('round-trips with splitName', () => {
    for (const emoji of EMOJI_CHOICES) {
      expect(splitName(joinName(emoji, 'Nome'))).toEqual({ emoji, text: 'Nome' })
    }
  })
})

describe('sorting', () => {
  it('goes by the words, not by the emoji in front', () => {
    // As plain strings 🏠 (U+1F3E0) sorts before 🔧 (U+1F527), which would put "Zebra" before "Abacate"
    const names = ['🏠 Zebra', '🔧 Abacate', 'Mala', '🍽️ Ação']

    expect([...names].sort(compareNames)).toEqual(['🔧 Abacate', '🍽️ Ação', 'Mala', '🏠 Zebra'])
  })

  it('sorts category objects the same way', () => {
    const categories = [{ name: '🏠 Zebra' }, { name: '🔧 Abacate' }]

    expect(categories.sort(compareCategories).map((c) => c.name)).toEqual(['🔧 Abacate', '🏠 Zebra'])
  })
})

describe('the emojis offered', () => {
  it('has no repeated emoji', () => {
    expect(new Set(EMOJI_CHOICES).size).toBe(EMOJI_CHOICES.length)
  })

  it('are each recognised as one emoji by splitName', () => {
    for (const emoji of EMOJI_CHOICES) {
      expect(splitName(emoji)).toEqual({ emoji, text: '' })
    }
  })
})

describe('searching categories', () => {
  it('ignores capitals, accents and the emoji of the name', () => {
    expect(searchKey('☕ Café')).toBe('cafe')
    expect(matchesSearch({ name: '☕ Café' }, 'CAFE')).toBe(true)
    expect(matchesSearch({ name: 'Água' }, 'agua')).toBe(true)
    expect(matchesSearch({ name: 'Água' }, 'luz')).toBe(false)
  })

  it('matches everything when nothing is typed', () => {
    expect(matchesSearch({ name: 'Qualquer' }, '')).toBe(true)
    expect(matchesSearch({ name: 'Qualquer' }, '  ')).toBe(true)
  })
})

describe('grouping categories', () => {
  const list = [
    { id: 1, name: 'Zebra', group_id: 'b', group_name: 'Moradia', group_position: 2 },
    { id: 2, name: '🛒 Mercado', group_id: 'a', group_name: 'Alimentação', group_position: 1 },
    { id: 3, name: 'Aluguel', group_id: 'b', group_name: 'Moradia', group_position: 2 },
    { id: 4, name: 'Água', group_id: 'b', group_name: 'Moradia', group_position: 2 },
  ]

  it('puts the groups in their own order and the categories A-Z inside each', () => {
    const groups = groupCategories(list)

    expect(groups.map((group) => group.name)).toEqual(['Alimentação', 'Moradia'])
    expect(groups[1].categories.map((category) => category.name)).toEqual(['Água', 'Aluguel', 'Zebra'])
  })

  it('does not change the list it is given', () => {
    const before = list.map((category) => category.id)
    groupCategories(list)
    expect(list.map((category) => category.id)).toEqual(before)
  })

  it('keeps categories with no group data together, A-Z, in a group with no name', () => {
    const groups = groupCategories([{ id: 1, name: 'B' }, { id: 2, name: 'A' }])

    expect(groups).toHaveLength(1)
    expect(groups[0].name).toBe('')
    expect(groups[0].categories.map((category) => category.name)).toEqual(['A', 'B'])
  })
})
