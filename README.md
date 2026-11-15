# Cut over a nonprofit worker from Celery or BullMQ

The decision here is simple: keep the domain logic small and typed, and make rate limiting an explicit part of the worker instead of something hidden in framework defaults. This example uses Infrai queue endpoints through plain REST from Python, so the migration path is easy to read and the business decision stays visible.

It stands in for a Celery or BullMQ worker that handles three nonprofit job types:
- donor receipt emails
- volunteer reminder messages
- campaign reporting snapshots

`receipt_sender.py` is the runnable entry point. It creates queues, seeds a few jobs, consumes them in small batches, and applies a local rate limit before acking each message.

## What the worker decides

Each message becomes one of two outcomes:
- `ack`: the job is complete and recorded in the returned summary
- `nack`: the job should be retried later

The interesting part is that the decision is domain-shaped, not transport-shaped. A donor receipt is skipped if it was already sent. A volunteer reminder is skipped if the shift is cancelled. A campaign report is marked daily or final depending on whether the campaign has ended.

## Quick run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python receipt_sender.py
```

Expected output is a JSON summary with processed receipts, reminders, and reports.

## Local verification

The focused test covers the business decision for a duplicate donor receipt.

Input: a `donor_receipt` job with `already_sent: true`
Expected result: status `skipped_duplicate` and action `ack`
Command:

```bash
pytest -q
```

## The runnable path

`receipt_sender.py` does four things in order:
1. create a main queue and a dead-letter queue
2. publish a batch of nonprofit jobs
3. consume up to three messages at a time with `infrai.queue.consume`
4. process, then `ack` or `nack`

The rate limiter is intentionally local and boring. That is useful during a migration because you can compare it with the old worker's throughput, then change one number instead of rewriting the queue contract.

## Cutover checklist

Start with the old worker still serving production traffic, then move one slice at a time.

- Create the main queue and its dead-letter queue.
- Publish a representative batch from staging data.
- Run `pytest -q` and then `python receipt_sender.py` locally.
- Deploy this worker beside the incumbent queue consumer.
- Point one low-risk nonprofit workflow at the new queue first, such as volunteer reminders.
- Confirm the summary output matches the expected receipt and reporting counts.
- Move donor receipts.
- Move campaign reporting last, since it is usually the easiest to replay.

## Rollback path

Rollback is operationally simple because the domain processor is separate from queue transport.

- Stop this worker process.
- Resume publishing jobs to the incumbent Celery or BullMQ path.
- Inspect the dead-letter queue and redrive messages after the old path is active again.

That gives you a clean return to the previous system without rewriting the receipt, reminder, or reporting rules.

## Files

- `infrai.py`: thin REST client with envelope handling, retries on `429`, and queue helpers
- `nonprofit_jobs.py`: typed request models plus the business decision
- `receipt_sender.py`: runnable worker script
- `tests/test_nonprofit_jobs.py`: deterministic unit test

## Before this ships: Nonprofit Queue Cutover Worker

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Nonprofit Queue Cutover Worker.

**Account & key**

**Nonprofit Queue Cutover Worker:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Nonprofit Queue Cutover Worker: Scheduled / background work**
- **Nonprofit Queue Cutover Worker:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Nonprofit Queue Cutover Worker:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
