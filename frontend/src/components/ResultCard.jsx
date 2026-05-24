import DataTable from './DataTable'
import SqlBlock from './SqlBlock'

export default function ResultCard({ result }) {
  const { question, answer, sql, data, error } = result
  const hasRows = Array.isArray(data?.rows) && data.rows.length > 0

  return (
    <article className="result-card">
      <div className="result-question-wrap">
        <p className="result-question">{question}</p>
      </div>

      <div className="result-answer-wrap">
        {error ? (
          <p className="result-error" role="alert">
            {error}
          </p>
        ) : (
          <>
            <p className="result-answer">{answer}</p>
            <SqlBlock sql={sql} />
            {hasRows && (
              <DataTable columns={data.columns} rows={data.rows} />
            )}
          </>
        )}
      </div>
    </article>
  )
}
