import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..config import llm_client, NVIDIA_MODEL
from ..database import engine
from ..models import Conversation, ConversationMessage, Expense, User
from ..security import get_current_user
from ..utils import utc_now

router = APIRouter()

SYSTEM_PROMPT = """You are an expense-tracking assistant. Answer directly and concisely using only tool results — never narrate your reasoning process in the answer. Always be polite and respectful in tone — use warm, courteous language (e.g. "Could you let me know...", "I'd be happy to help with...") rather than blunt or robotic phrasing, while staying concise.

    Valid expense categories are: Food, Transport, Bills, Entertainment, Shopping, Health, Rent, Travel, Education, Miscellaneous.
    Recognized time periods (only pass these to the tool): "this week", "last week", "this month", "last month", "this year", "last year", or an explicit "YYYY-MM-DD to YYYY-MM-DD" range.

    If there is more than one thing to clarify, ask about ONLY ONE at a time — never combine multiple clarifying questions into a single message.

    Step 1 — check the time period first. If the question doesn't specify one of the recognized time periods above:
    - Do NOT call get_expenses_summary.
    - Instead, call the ask_clarifying_question tool with a short question string and exactly two concrete options (e.g. "This week" and "This month"), marking exactly one option's "recommended" field true. Mention in the question text that the user can also give their own custom range instead (e.g. "or tell me a specific date range like 2024-01-01 to 2024-03-31").
    - Do NOT mention the category ambiguity in this message, even if the category is also unclear — that will be asked in a separate follow-up once the time period is known.
    - Stop here. Do not guess or call get_expenses_summary until the user replies.

    Step 2 — this step ONLY applies if the user explicitly mentioned a specific category-like word that does NOT match the valid list above (e.g. "electronics", "groceries", "clothes"). If the user simply did not mention any category at all, that is NOT ambiguous — it means "all categories combined." In that case, skip straight to Step 3.
    - If a mismatched category word was used: briefly say the exact category doesn't exist, offer exactly two concrete category options marking one "Recommended", call the tool with the recommended category and the given time period, and give that number immediately — don't wait for confirmation. Mention the user can ask about the other option if it fits better.

    Step 3 — if the time period is clear and there is no category ambiguity (either a valid category was given, or none was given at all): call the tool and give a direct, concise answer with no extra commentary."""


def parse_date_range(date_range: Optional[str]):
    if not date_range:
        return None, None

    now = utc_now()
    text = date_range.strip().lower()

    if text == "this week":
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if text == "last week":
        this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_end = this_week_start - timedelta(seconds=1)
        last_week_start = (last_week_end - timedelta(days=last_week_end.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return last_week_start, last_week_end
    if text == "this month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if text == "last month":
        first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = first_this_month - timedelta(seconds=1)
        start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, last_month_end
    if text == "this year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if text == "last year":
        start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(year=now.year - 1, month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
        return start, end
    if " to " in text:
        start_str, end_str = text.split(" to ")
        start = datetime.fromisoformat(start_str.strip()).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_str.strip()).replace(tzinfo=timezone.utc)
        return start, end

    return None, None


def get_expenses_summary(user_id: int, category: Optional[str] = None, date_range: Optional[str] = None) -> str:
    with Session(engine) as session:
        query = select(Expense).where(Expense.user_id == user_id)
        if category:
            query = query.where(Expense.category == category)
        start, end = parse_date_range(date_range)
        if start:
            query = query.where(Expense.date >= start)
        if end:
            query = query.where(Expense.date <= end)

        expenses = session.exec(query).all()
        if not expenses:
            return "No expense found"

        total_amount = sum(expense.amount for expense in expenses)
        breakdown = "\n".join([f"- {e.category}: ${e.amount} {e.date} ({e.description or 'no description'})" for e in expenses])
        return f"Total: ${total_amount}\n\nDetails:\n{breakdown}"


expense_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_expenses_summary",
            "description": "Get a summary of the user's expenses, optionally filtered by category and date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": ["string", "null"],
                        "enum": ["Food", "Transport", "Bills", "Entertainment", "Shopping", "Health", "Rent", "Travel", "Education", "Miscellaneous", None],
                        "description": "Optional category to filter by. Must be one of the listed categories — e.g. clothing purchases fall under 'Shopping'."
                    },
                    "date_range": {
                        "type": ["string", "null"],
                        "description": "Optional date range to filter by, e.g. '2023-01-01 to 2023-01-31', 'last month', 'this year'"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_clarifying_question",
            "description": "Ask the user a clarifying question with a small set of concrete options to choose from, when their request doesn't give enough information for get_expenses_summary to run (e.g. an unrecognized or missing time period).",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The clarifying question to show the user, e.g. 'Which time period would you like?'"
                    },
                    "options": {
                        "type": "array",
                        "description": "2-3 concrete options the user can tap to answer. Exactly one should have recommended set to true.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "The option text shown to the user, e.g. 'This week'"},
                                "recommended": {"type": "boolean", "description": "Whether this is the recommended option"}
                            },
                            "required": ["label", "recommended"]
                        }
                    }
                },
                "required": ["question", "options"]
            }
        }
    }
]


@router.post("/ask")
def ask_about_expenses(question: dict, current_user: User = Depends(get_current_user)):
    user_question = question["question"]
    conversation_id = question.get("conversation_id")

    with Session(engine) as session:
        if conversation_id:
            conversation = session.get(Conversation, conversation_id)
            if not conversation or conversation.user_id != current_user.id:
                raise HTTPException(status_code=404, detail="Conversation not found")

            rows = session.exec(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.id)
            ).all()

            messages = []
            for row in rows:
                if row.role == "assistant" and row.tool_calls_json:
                    messages.append({"role": "assistant", "content": row.content, "tool_calls": json.loads(row.tool_calls_json)})
                elif row.role == "tool":
                    messages.append({"role": "tool", "tool_call_id": row.tool_call_id, "content": row.content})
                else:
                    messages.append({"role": row.role, "content": row.content})
        else:
            conversation = Conversation(user_id=current_user.id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            session.add(ConversationMessage(conversation_id=conversation.id, role="system", content=SYSTEM_PROMPT))

        messages.append({"role": "user", "content": user_question})
        session.add(ConversationMessage(conversation_id=conversation.id, role="user", content=user_question))
        session.commit()

        for _ in range(4):
            response = llm_client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=messages,
                tools=expense_tools,
                max_tokens=2000
            )

            reply = response.choices[0].message
            messages.append(reply)

            tool_calls_json = json.dumps([tc.model_dump() for tc in reply.tool_calls]) if reply.tool_calls else None
            session.add(ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=reply.content or "",
                tool_calls_json=tool_calls_json
            ))
            session.commit()

            if not reply.tool_calls:
                return {"answer": reply.content, "conversation_id": conversation.id}

            clarifying_result = None
            for tool_call in reply.tool_calls:
                arguments = json.loads(tool_call.function.arguments)

                if tool_call.function.name == "ask_clarifying_question":
                    clarifying_result = {
                        "answer": arguments.get("question"),
                        "options": arguments.get("options", []),
                    }
                    tool_result = "Waiting for the user's choice."
                else:
                    tool_result = get_expenses_summary(user_id=current_user.id, category=arguments.get("category"), date_range=arguments.get("date_range"))

                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_result})
                session.add(ConversationMessage(
                    conversation_id=conversation.id,
                    role="tool",
                    content=tool_result,
                    tool_call_id=tool_call.id
                ))
            session.commit()

            if clarifying_result:
                return {**clarifying_result, "conversation_id": conversation.id}

        return {"answer": None, "conversation_id": conversation.id}
