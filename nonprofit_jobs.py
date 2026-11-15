from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class DonorReceiptJob(BaseModel):
    kind: Literal["donor_receipt"]
    donation_id: str
    donor_email: str
    amount_cents: int
    already_sent: bool = False


class VolunteerReminderJob(BaseModel):
    kind: Literal["volunteer_reminder"]
    volunteer_id: str
    volunteer_name: str
    shift_start_iso: str
    cancelled: bool = False


class CampaignReportJob(BaseModel):
    kind: Literal["campaign_report"]
    campaign_id: str
    campaign_name: str
    total_raised_cents: int
    goal_cents: int
    campaign_end_date: date
    today: date


NonprofitJob = Annotated[
    Union[DonorReceiptJob, VolunteerReminderJob, CampaignReportJob],
    Field(discriminator="kind"),
]


class JobOutcome(BaseModel):
    action: Literal["ack", "nack"]
    status: str
    summary: str


def decide_job(job: NonprofitJob) -> JobOutcome:
    if isinstance(job, DonorReceiptJob):
        if job.already_sent:
            return JobOutcome(action="ack", status="skipped_duplicate", summary=f"receipt {job.donation_id} already sent")
        return JobOutcome(action="ack", status="receipt_sent", summary=f"receipt for {job.donor_email} amount={job.amount_cents}")

    if isinstance(job, VolunteerReminderJob):
        if job.cancelled:
            return JobOutcome(action="ack", status="shift_cancelled", summary=f"no reminder for {job.volunteer_id}")
        return JobOutcome(action="ack", status="reminder_sent", summary=f"reminder for {job.volunteer_name} at {job.shift_start_iso}")

    if job.today >= job.campaign_end_date:
        reached_goal = job.total_raised_cents >= job.goal_cents
        suffix = "goal_hit" if reached_goal else "goal_open"
        return JobOutcome(action="ack", status=f"final_report_{suffix}", summary=f"final report for {job.campaign_name}")

    return JobOutcome(action="ack", status="daily_report", summary=f"daily report for {job.campaign_name}")
