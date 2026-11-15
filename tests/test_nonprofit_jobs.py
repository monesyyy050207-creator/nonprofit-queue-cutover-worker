from nonprofit_jobs import DonorReceiptJob, decide_job


def test_duplicate_donor_receipt_is_acked_and_marked_skipped() -> None:
    job = DonorReceiptJob(
        kind="donor_receipt",
        donation_id="don-1002",
        donor_email="grace@example.org",
        amount_cents=7500,
        already_sent=True,
    )

    outcome = decide_job(job)

    assert outcome.action == "ack"
    assert outcome.status == "skipped_duplicate"
    assert outcome.summary == "receipt don-1002 already sent"
