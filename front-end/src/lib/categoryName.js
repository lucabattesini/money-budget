// A category name may start with an emoji ("🛒 Supermercado"): the emoji is part of the name, not a separate field.
// These helpers split it and put it together again, and sort by the words only, so lists stay A-Z whatever the emoji.

// What an emoji is made of: pictographs, skin tones, flags, and the invisible joiners and variation selectors.
const EMOJI = String.raw`(?:[\p{Extended_Pictographic}\p{Emoji_Modifier}\p{Regional_Indicator}]|\u200d|\ufe0f)`
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

// The emojis offered when adding or editing a category, by theme.
export const EMOJI_CHOICES = [
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
  // everything else
  "🐾", "🐶", "🐱", "🌱", "👶", "🎓", "🛍️", "👕", "💄", "✂️", "🛡️", "🚨", "📦", "➕", "🔄", "🏧", "❤️", "⭐", "🔔",
]
