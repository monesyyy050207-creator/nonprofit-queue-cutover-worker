import json
import time
from typing import Any, Dict, List

import infrai
from nonprofit_jobs import decide_job, DonorReceiptJob, VolunteerReminderJob, CampaignReportJob

MAIN_QUEUE = "nonprofit-jobs"
DLQ_QUEUE = "nonprofit-jobs-dlq"


class LocalRateLimiter:
    def __init__(self, max_per_second: int):
        self.max_per_second = max_per_second
        self.window_started = time.monotonic()
        self.used = 0

    def wait_turn(self) -> None:
        now = time.monotonic()
        elapsed = now - self.window_started
        if elapsed >= 1.0:
            self.window_started = now
            self.used = 0
        if self.used >= self.max_per_second:
            time.sleep(max(0.0, 1.0 - elapsed))
            self.window_started = time.monotonic()
            self.used = 0
        self.used += 1


def ensure_queues() -> None:
    infrai.queue.create(name=DLQ_QUEUE)
    infrai.queue.create(name=MAIN_QUEUE, dead_letter_queue=DLQ_QUEUE, max_retries=3)


def seed_jobs() -> None:
    messages: List[Dict[str, Any]] = [
        {
            "id": "receipt-001",
            "payload": {
                "kind": "donor_receipt",
                "donation_id": "don-1001",
                "donor_email": "ada@example.org",
                "amount_cents": 5000,
                "already_sent": False
            }
        },
        {
            "id": "receipt-002",
            "payload": {
                "kind": "donor_receipt",
                "donation_id": "don-1002",
                "donor_email": "grace@example.org",
                "amount_cents": 7500,
                "already_sent": True
            }
        },
        {
            "id": "volunteer-001",
            "payload": {
                "kind": "volunteer_reminder",
                "volunteer_id": "vol-42",
                "volunteer_name": "Mina",
                "shift_start_iso": "2026-03-10T09:00:00Z",
                "cancelled": False
            }
        },
        {
            "id": "campaign-001",
            "payload": {
                "kind": "campaign_report",
                "campaign_id": "camp-7",
                "campaign_name": "Spring Drive",
                "total_raised_cents": 120000,
                "goal_cents": 100000,
                "campaign_end_date": "2026-03-01",
                "today": "2026-03-02"
            }
        }
    ]
    infrai.queue.publish_batch(queue=MAIN_QUEUE, messages=messages)


def process_once(max_messages: int = 3) -> Dict[str, Any]:
    limiter = LocalRateLimiter(max_per_second=2)
    batch = infrai.queue.consume(queue=MAIN_QUEUE, max_messages=max_messages, visibility_timeout=30)
    items = batch["data"] or []
    processed = []

    for message in items:
        limiter.wait_turn()
        payload = message["payload"]
        kind = payload["kind"]
        if kind == "donor_receipt":
            job = DonorReceiptJob.model_validate(payload)
        elif kind == "volunteer_reminder":
            job = VolunteerReminderJob.model_validate(payload)
        else:
            job = CampaignReportJob.model_validate(payload)

        outcome = decide_job(job)
        if outcome.action == "ack":
            infrai.queue.ack(queue=MAIN_QUEUE, message_id=message["message_id"])
        else:
            infrai.queue.nack(queue=MAIN_QUEUE, message_id=message["message_id"])

        processed.append(
            {
                "message_id": message["message_id"],
                "kind": kind,
                "status": outcome.status,
                "summary": outcome.summary,
            }
        )

    return {"processed": processed, "count": len(processed)}


if __name__ == "__main__":
    ensure_queues()
    seed_jobs()
    summary = process_once()
    print(json.dumps(summary, indent=2))
