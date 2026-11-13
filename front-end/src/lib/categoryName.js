// A category name may start with an emoji ("🛒 Supermercado"): the emoji is part of the name, not a separate field.
// These helpers split it and put it together again, and sort by the words only, so lists stay A-Z whatever the emoji.

// What the start of a name may be made of besides its words. This is exactly the rule the server uses
// (back-end/api/utils/category_names.py), so the page and the server split a name the same way: symbols (Unicode
// category So: pictographs, flags, arrows...), modifier symbols (Sk: skin tones), the zero-width joiner and the
// emoji variation selector.
const EMOJI = String.raw`(?:[\p{So}\p{Sk}]|\u200d|\ufe0f)`
const LEADING_EMOJI = new RegExp(`^\\s*(${EMOJI}+)\\s*`, "u")

/** "🛒 Supermercado" -> { emoji: "🛒", text: "Supermercado" }. A name without emoji has an empty emoji. */
export function splitName(name) {
  const value = name ?? ""
  const match = value.match(LEADING_EMOJI)
  return match ? { emoji: match[1], text: value.slice(match[0].length).trim() } : { emoji: "", text: value.trim() }
}

/** The name without its emoji. */
export const plainName = (name) => splitName(name).text

/** An emoji (or none) and the words, as one name: "🛒" + "Supermercado" -> "🛒 Supermercado". */
export const joinName = (emoji, text) => (emoji ? `${emoji} ${text}` : text)

/** For sort(): A-Z by the words, in Brazilian Portuguese order, ignoring the emoji. */
export const compareNames = (a, b) => plainName(a).localeCompare(plainName(b), "pt-BR")

/** For sort() on category objects. */
export const compareCategories = (a, b) => compareNames(a.name, b.name)

/** The words of a name as a search sees them: no emoji, no accents, no capitals ("☕ Café" -> "cafe"). */
export const searchKey = (text) => plainName(text).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase()

/** Does the category match what was typed? An empty search matches everything. */
export const matchesSearch = (category, typed) => searchKey(category.name).includes(searchKey(typed).trim())

/**
 * The categories under their groups, as every list shows them: groups in their own order (group_position), categories
 * A-Z inside a group. Categories that carry no group at all (older data) come as one group with no name.
 * -> [{ id, name, categories }]
 */
export function groupCategories(categories) {
  const groups = new Map()
  for (const category of categories) {
    const key = category.group_id ?? category.group_name ?? ""
    if (!groups.has(key)) {
      groups.set(key, { id: key, name: category.group_name ?? "", position: category.group_position ?? Infinity, categories: [] })
    }
    groups.get(key).categories.push(category)
  }
  return [...groups.values()]
    .sort((a, b) => a.position - b.position || compareNames(a.name, b.name))
    .map((group) => ({ id: group.id, name: group.name, categories: [...group.categories].sort(compareCategories) }))
}

// The emojis offered when adding or editing a category, by theme.
const EMOJI_LIST = [
  // money
  "💰", "💵", "💳", "🏦", "📈", "📉", "🧾", "💸", "🪙", "💼",
  // home
  "🏠", "🛋️", "💡", "🚿", "🔧", "🧹", "📶", "📱", "🔌", "🧺",
  // food
  "🛒", "🍽️", "🍕", "🍔", "☕", "🍺", "🥗", "🍎", "🧁", "🥖",
  // transport
  "🚗", "⛽", "🚌", "🚆", "✈️", "🚲", "🛵", "🅿️", "🚕", "🛣️",
  // health and care
  "💊", "🩺", "🦷", "🏋️", "🧴", "💆", "🧘", "🏥",
  // leisure
  "🎬", "🎮", "🎵", "🎨", "📺", "🎉", "🎁", "🏖️", "⚽", "📚",
  // more food and drink
  "🍞", "🥩", "🍗", "🍝", "🍣", "🌮", "🥪", "🍜", "🍰", "🍫", "🍦", "🍩", "🍪", "🥛", "🧃", "🍷", "🍹", "🍾", "🥕", "🍌", "🍇", "🥑", "🧀", "🥚",
  // more home and utilities
  "🛏️", "🪑", "🚪", "🪟", "🔑", "🧯", "🧽", "🧼", "🪣", "🔥", "💧", "🌡️", "📡", "🖥️", "💻", "🖨️", "🔋", "🪴",
  // more transport and travel
  "🚓", "🚑", "🚐", "🚚", "🚜", "🏍️", "🚇", "🚢", "⛵", "🛶", "🧳", "🗺️", "🏨", "🏕️", "🎒", "🛂", "🚏", "🛞",
  // more health, care and fitness
  "💉", "🩹", "🧬", "👓", "🏃", "🚴", "🏊", "🥊", "🧖", "💅", "💇", "🪒", "🧻", "🩻",
  // more leisure and culture
  "🎭", "🎤", "🎧", "🎸", "🎹", "🎻", "🎲", "🧩", "🎯", "🎳", "🎟️", "📷", "🎥", "🎪", "🎡", "🏟️", "🏀", "🎾", "🏄", "⛷️", "🎣", "🏕️", "🪁",
  // work, study and money
  "💎", "🧮", "📊", "🗂️", "📁", "📝", "✏️", "📖", "🔬", "🔭", "🖊️", "🏢", "🏭", "⚖️", "🤝", "📞", "✉️", "📬", "🪪", "🧾",
  // family, pets and celebrations
  "👨‍👩‍👧", "🧒", "🧓", "🍼", "🧸", "🎂", "🎈", "🎄", "🎃", "💐", "💍", "💒", "🐕", "🐈", "🐟", "🐦", "🐴", "🦮", "🪺",
  // clothes and shopping
  "👗", "👖", "👟", "👠", "👜", "🧥", "🧢", "⌚", "💍", "🕶️", "🎽", "🧦", "🏷️", "🛒",
  // giving, taxes and everything else
  "🐾", "🌱", "🎓", "🛍️", "💄", "✂️", "🛡️", "🚨", "📦", "➕", "🔄", "🏧", "❤️", "⭐", "🔔", "🙏", "🤲", "⛪", "🕌", "🕍", "🏛️", "⚠️", "❓", "🆘", "♻️", "🌍", "🌧️", "☀️", "🔒", "🧰", "🛠️", "🏦",
]
export const EMOJI_CHOICES = [...new Set(EMOJI_LIST)] // an emoji that fits two themes is offered once
