"""Seung's First Axon Workflow.

A three-step pipeline: a Delegate validates the contact record, an AI Team
analyzes it, then a deterministic Delegate transforms the analysis into a
final report.

Usage:
    uv run axon graph  seungs_first_workflow            # preview the flow
    uv run axon deploy seungs_first_workflow -n <your-namespace>
    uv run axon run    seungs_first_workflow -n <your-namespace> --wait
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from axon.lib import Agent, Context, Step, Team, Variable, Workflow, delegate


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ContactInput(BaseModel):
    """Validated input for the workflow."""

    name: str = Field(description="Full name of the contact")
    email: str = Field(description="Email address")
    department: str | None = Field(default=None, description="Department name")
    role: str | None = Field(default=None, description="Job title / role")


class ContactAnalysis(BaseModel):
    """Structured output produced by the AI team."""

    summary: str = Field(description="One-sentence summary of this contact")
    seniority: str = Field(description="Estimated seniority: junior, mid, senior, staff, principal, executive")
    suggested_greeting: str = Field(description="A personalized greeting for this contact")


# Note: the delegates below deliberately avoid the Pydantic models above.
# When the SDK inlines a module-level class into delegate code, it does not
# carry over the imports the class body needs (`BaseModel`, `Field`), so the
# delegate fails on the platform with `NameError: name 'BaseModel' is not
# defined`. Plain `json` + dicts keep each delegate self-contained.


# ---------------------------------------------------------------------------
# Step 1: Delegate — validate the raw input
# ---------------------------------------------------------------------------
# This is the only step that consumes the workflow input `raw_input`.
# If several steps declare the same workflow input, `axon run` binds it to
# just one of them (the last), and the root step gets nothing:
# "no input variable for `raw_input`".
@delegate(
    description="Validate the raw contact record and emit a normalized contact.",
    outputs=[Variable(name="contact", type="String")],
)
def validate_input(context: Context, raw_input: str) -> dict:
    """Parse and normalize the incoming contact record."""
    data = json.loads(raw_input)
    if not isinstance(data, dict):
        raise ValueError(f"raw_input must be a JSON object, got {type(data).__name__}")
    for key in ("name", "email"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"raw_input is missing required string field '{key}'")
    contact = {
        "name": data["name"],
        "email": data["email"],
        "department": data.get("department"),
        "role": data.get("role"),
    }
    contact_json = json.dumps(contact)
    # The platform only persists outputs written via save_variable;
    # a returned dict alone leaves `contact` unset.
    context.save_variable("contact", contact_json)
    return {"contact": contact_json}


# ---------------------------------------------------------------------------
# Step 2: AI Team — analyze the contact
# ---------------------------------------------------------------------------
analysis_team = Team(
    name="Contact_Analyzer",
    goal="Analyze this contact record and produce a structured assessment:\n\n{{contact}}",
    results="A ContactAnalysis saved to the 'analysis' variable.",
    agents=[
        Agent.speaker_selector(model="gpt-4o-mini"),
        Agent(
            name="Analyst",
            persona="You are a concise business analyst who profiles contacts.",
            skills=(
                "1. Read the contact data in the goal.\n"
                "2. Produce a JSON ContactAnalysis matching the Response Format.\n"
                "3. Save the result to the 'analysis' variable.\n"
                "4. Say TERMINATE_TEAM when done."
            ),
            model="gpt-4o-mini",
            tools=["save_variable"],
            output_type=ContactAnalysis,
            output_variable="analysis",
        ),
    ],
    inputs=[Variable(name="contact", type="String")],
    outputs=[Variable(name="analysis", type="String")],
)


# ---------------------------------------------------------------------------
# Step 3: Delegate — deterministic formatting
# ---------------------------------------------------------------------------
@delegate(
    description="Combine the original input with the AI analysis into a final report.",
    outputs=[Variable(name="report", type="String")],
)
def format_report(context: Context, contact: str, analysis: str) -> dict:
    """Merge AI analysis with the original contact data."""
    person = json.loads(contact)
    ai = json.loads(analysis)

    report = {
        "contact_name": person["name"],
        "contact_email": person["email"],
        "department": person.get("department"),
        "role": person.get("role"),
        "ai_summary": ai["summary"],
        "ai_seniority": ai["seniority"],
        "ai_greeting": ai["suggested_greeting"],
        "processed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    report_json = json.dumps(report, indent=2)
    context.save_variable("report", report_json)
    context.status_message(f"Report generated for {person['name']}")
    return {"report": report_json}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
workflow = Workflow(
    name="Seungs_First_Workflow",
    description="AI-analyze a contact record, then format a structured report.",
    steps=[
        Step(entity=validate_input),
        Step(entity=analysis_team),
        Step(entity=format_report),
    ],
    inputs=[Variable(name="raw_input", type="String", direction="Input")],
    outputs=[Variable(name="report", type="String", direction="Output")],
)

DEFAULT_INPUT = {
    "raw_input": ContactInput(
        name="Alice Johnson",
        email="alice@example.com",
        department="Engineering",
        role="Staff Engineer",
    ).model_dump_json()
}
