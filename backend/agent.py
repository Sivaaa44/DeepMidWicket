import os
import re
from groq import Groq
from dotenv import load_dotenv
from database import run_query, get_schema

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_sql(question: str) -> str:
    """
    Takes a natural language cricket question and returns a SQL query.
    """
    prompt = f"""You are an expert cricket analyst and SQL writer.
Given the database schema below, write a single valid SQLite SELECT query to answer the user's question.

{get_schema()}

Rules:
- Return ONLY the raw SQL query, no explanation, no markdown, no backticks
- Only use SELECT, never INSERT/UPDATE/DELETE
- Use LIKE '%name%' for player name searches
- Use over BETWEEN 0 AND 5 for powerplay, 15 AND 19 for death overs
- Always use meaningful column aliases for clarity
- Limit results to 20 rows unless the question asks for a single value

User question: {question}

SQL:"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,  # low temp for deterministic SQL
        max_completion_tokens=512,
    )

    sql = response.choices[0].message.content.strip()

    # Strip markdown code blocks if model adds them anyway
    sql = re.sub(r"```sql|```", "", sql).strip()

    return sql


def generate_answer(question: str, columns: list, rows: list) -> str:
    """
    Takes the SQL results and converts them into a natural language answer.
    """
    if not rows:
        return "I couldn't find any data matching your question. Try rephrasing or check the player/team name."

    # Format results as a simple text table for the prompt
    results_text = " | ".join(columns) + "\n"
    results_text += "-" * 60 + "\n"
    for row in rows[:20]:
        results_text += " | ".join(str(v) for v in row.values()) + "\n"

    prompt = f"""You are a cricket analyst giving insights based on IPL data.

The user asked: "{question}"

Here are the query results:
{results_text}

Give a clear, concise, natural language answer based on this data.
- Lead with the direct answer
- Highlight interesting numbers or patterns
- Keep it under 100 words
- Sound like a cricket analyst, not a robot"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_completion_tokens=300,
    )

    return response.choices[0].message.content.strip()


def ask(question: str) -> dict:
    """
    Main agent function. Takes a question, returns SQL + answer + raw data.
    """
    try:
        sql = generate_sql(question)
        columns, rows = run_query(sql)
        answer = generate_answer(question, columns, rows)

        return {
            "question": question,
            "sql": sql,
            "answer": answer,
            "data": {"columns": columns, "rows": rows}
        }

    except Exception as e:
        return {
            "question": question,
            "sql": None,
            "answer": f"Sorry, I ran into an error: {str(e)}",
            "data": None
        }