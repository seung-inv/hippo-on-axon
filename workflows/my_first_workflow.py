"""My First Axon Workflow.

A two-step pipeline: an AI Team analyzes a contact record, then a
deterministic Delegate transforms the analysis into a final report.

Usage:
    uv run axon graph  workflows.my_first_workflow            # preview the flow
    uv run axon deploy workflows.my_first_workflow -n <your-namespace>
    uv run axon run    workflows.my_first_workflow -n <your-namespace> --wait
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


class FinalReport(BaseModel):
    """Final report combining input data with AI analysis."""

    contact_name: str
    contact_email: str
    department: str | None
    role: str | None
    ai_summary: str
    ai_seniority: str
    ai_greeting: str
    processed_at: str


# ---------------------------------------------------------------------------
# Step 1: AI Team — analyze the contact
# ---------------------------------------------------------------------------
analysis_team = Team(
    name="Contact_Analyzer",
    goal="Analyze this contact record and produce a structured assessment:\n\n{{raw_input}}",
    results="A ContactAnalysis saved to the 'analysis' variable.",
    agents=[
        Agent.speaker_selector(),
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
    inputs=[Variable(name="raw_input", type="String")],
    outputs=[Variable(name="analysis", type="String")],
)


# ---------------------------------------------------------------------------
# Step 2: Delegate — deterministic formatting
# ---------------------------------------------------------------------------
@delegate(
    description="Combine the original input with the AI analysis into a final report.",
    outputs=[Variable(name="report", type="String")],
)
def format_report(context: Context, raw_input: str, analysis: str) -> dict:
    """Merge AI analysis with the original contact data."""
    contact = ContactInput.model_validate_json(raw_input)
    ai = ContactAnalysis.model_validate_json(analysis)

    report = FinalReport(
        contact_name=contact.name,
        contact_email=contact.email,
        department=contact.department,
        role=contact.role,
        ai_summary=ai.summary,
        ai_seniority=ai.seniority,
        ai_greeting=ai.suggested_greeting,
        processed_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    context.status_message(f"Report generated for {contact.name}")
    return {"report": report.model_dump_json(indent=2)}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
workflow = Workflow(
    name="My_First_Workflow",
    description="AI-analyze a contact record, then format a structured report.",
    steps=[
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
