import { toNumber } from './format'

const LOWER_BETTER = /economy|econ|bowling.?av|bowling.?sr|average.?against|avg.?against|conceded|dot.?balls.?faced|dismissals|balls.?per.?boundary/i
const HIGHER_BETTER = /runs|wickets|strike|sr|six|four|centur|fift|high|score|win|rate|boundar|innings|matches|not.?out|dot/i

/** Whether a smaller value is better for this stat (economy, bowling average, ...). */
export function isLowerBetter(statName, context = 'batting') {
  const s = String(statName).toLowerCase()
  // In a batter-vs-bowler matchup, dismissals favour the bowler; elsewhere "dismissals" is a batting weakness.
  if (LOWER_BETTER.test(s)) return true
  if (HIGHER_BETTER.test(s)) return false
  return context === 'bowling'
}

/** @returns {'left' | 'right' | 'tie' | null} */
export function compareValues(statName, left, right) {
  const a = toNumber(left)
  const b = toNumber(right)
  if (a === null || b === null) return null
  if (a === b) return 'tie'
  if (isLowerBetter(statName)) return a < b ? 'left' : 'right'
  return a > b ? 'left' : 'right'
}

/** Columns that are identifiers or counts of context rather than performance. */
export function isNeutralStat(col) {
  return /(^|_)(id|match_id|match_number|matches|innings|balls|balls_faced|balls_bowled|season|year)$/i.test(String(col))
}
