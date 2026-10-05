import { toNumber } from './format'

const TEMPORAL = /^(season|year|date|month|day)$/i
const ID_LIKE = /(^|_)(id|match_id|match_number|rank)$/i
const PRIORITY = [
  /^total_?runs$/, /^runs$/, /^wickets$/, /^total_?wickets$/, /win_?(pct|percentage)/, /^wins$/,
  /strike_?rate/, /economy/, /sixes/, /fours/, /average/, /count/, /total/,
]

function isMonotonic(values) {
  if (values.some((v) => v === null)) return false
  const distinct = new Set(values).size > 1
  const desc = values.every((v, i) => i === 0 || v <= values[i - 1])
  const asc = values.every((v, i) => i === 0 || v >= values[i - 1])
  return distinct && (desc || asc)
}

/** Inspect a result set and describe how it can be visualised. */
export function analyzeResult(columns = [], rows = []) {
  const numeric = []
  const text = []
  for (const col of columns) {
    const values = rows.map((r) => r[col]).filter((v) => v !== null && v !== undefined && v !== '')
    if (values.length && values.every((v) => toNumber(v) !== null)) numeric.push(col)
    else text.push(col)
  }

  let label = text[0] ?? null
  // A numeric season/year column works as the x-axis label.
  const temporalCol = columns.find((c) => TEMPORAL.test(c))
  if (temporalCol && (!label || TEMPORAL.test(temporalCol))) label = temporalCol
  if (!label) {
    const yearLike = numeric.find((c) => rows.every((r) => /^(19|20)\d\d$/.test(String(r[c]))))
    if (yearLike) label = yearLike
  }

  const metrics = numeric.filter((c) => c !== label && !ID_LIKE.test(c))
  const temporal = !!label && (TEMPORAL.test(label) || rows.every((r) => /^(19|20)\d\d(\/\d\d)?$/.test(String(r[label]))))

  let defaultMetric = metrics[0] ?? null
  // If the rows are ordered by one metric (ORDER BY x DESC), that's what the question was about.
  const rankedBy = !temporalCol && rows.length >= 3 ? metrics.find((m) => isMonotonic(rows.map((r) => toNumber(r[m])))) : null
  for (const re of rankedBy ? [] : PRIORITY) {
    const hit = metrics.find((m) => re.test(m.toLowerCase()))
    if (hit) {
      defaultMetric = hit
      break
    }
  }

  if (rankedBy) defaultMetric = rankedBy
  const chartable = !!label && metrics.length > 0 && rows.length >= 2 && rows.length <= 40
  return { label, metrics, numeric, text, temporal, defaultMetric, chartable }
}

export function chartRows(rows, label, metric, temporal) {
  const data = rows
    .map((r) => ({ label: String(r[label] ?? '—'), value: toNumber(r[metric]), raw: r }))
    .filter((d) => d.value !== null)
  if (temporal) data.sort((a, b) => a.label.localeCompare(b.label))
  return data
}
