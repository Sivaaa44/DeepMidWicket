const LOWER_BETTER =
  /economy|econ|bowling.?avg|bowling.?average|average against|avg against|against|conceded|balls per/i
const HIGHER_BETTER =
  /runs|wickets|strike|sr|six|four|centur|high|score|win|rate|boundar|fifty|innings|matches|not out/i

export function isLowerBetter(statName) {
  const s = String(statName).toLowerCase()
  if (LOWER_BETTER.test(s)) return true
  if (HIGHER_BETTER.test(s)) return false
  return false
}

export function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

/** @returns {'left' | 'right' | 'tie' | null} */
export function compareValues(statName, left, right) {
  const a = toNumber(left)
  const b = toNumber(right)
  if (a === null || b === null) return null
  if (a === b) return 'tie'
  const lowerBetter = isLowerBetter(statName)
  if (lowerBetter) return a < b ? 'left' : 'right'
  return a > b ? 'left' : 'right'
}

export function formatStatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
  }
  return String(value)
}

export function findDismissalLine(columns, rows) {
  for (const row of rows) {
    for (const col of columns) {
      const label = String(col).toLowerCase()
      if (label.includes('dismiss') || label.includes('wicket') && label.includes('times')) {
        const val = row[col]
        if (val !== null && val !== undefined && val !== '') {
          return `Dismissed ${val} times`
        }
      }
    }
  }
  return null
}
