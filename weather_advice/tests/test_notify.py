"""Alert formatting, and the setup warnings that keep a dead channel visible."""

from datetime import datetime

from weather_advice.models import Decision
from weather_advice.notify import Notifier

OPEN_AT = datetime(2026, 10, 5, 22, 0)
CLOSE_AT = datetime(2026, 10, 6, 7, 0)


def _open_decision(**kw):
    base = dict(night="2026-10-05", route="open", open_at=OPEN_AT,
                close_at=CLOSE_AT, hours=9.0, low_f=70, high_f=76,
                wake_at=CLOSE_AT)
    base.update(kw)
    return Decision(**base)


def _notifier(**kw):
    base = dict(smtp_host="smtp.example.com", smtp_user="u",
                smtp_password="p", email_to=["me@example.com"])
    base.update(kw)
    return Notifier(**base)


def test_the_verdict_lands_before_a_phone_truncates_the_subject():
    """A lock screen shows roughly 40 characters, so the answer and the hours
    must both appear early."""
    subject = Notifier.subject_for(_open_decision())
    assert subject.startswith("[windows] Open tonight")
    assert "9h" in subject[:45]


def test_the_sms_is_short_enough_to_read_without_unlocking():
    text = Notifier.sms_for(_open_decision())
    assert len(text) <= 160
    assert "10:00pm-7:00am" in text


def test_a_warm_tail_is_mentioned_in_the_text():
    text = Notifier.sms_for(
        _open_decision(warm_after=datetime(2026, 10, 6, 6, 0)))
    assert "warm after 6:00am" in text


def test_times_use_a_portable_twelve_hour_format():
    """strftime("%-I") is glibc-only and raises on Windows, which is where
    this runs. Midnight and noon are the cases that expose a hand-rolled
    version."""
    d = _open_decision(open_at=datetime(2026, 10, 5, 0, 5),
                       close_at=datetime(2026, 10, 5, 12, 0))
    text = Notifier.sms_for(d)
    assert "12:05am" in text and "12:00pm" in text


def test_a_shut_night_is_never_alerted():
    n = _notifier()
    assert n.handles("shut") is False
    assert n.send(Decision(night="2026-10-05", route="shut")) is False


def test_marginal_nights_do_not_buzz_the_phone_by_default():
    """Real, but a hassle -- so it goes to the inbox, not the lock screen."""
    n = _notifier(sms_to=["5551234567@vtext.com"])
    assert "marginal" in n.routes
    assert "marginal" not in n.sms_routes


def test_an_unconfigured_notifier_reports_failure_rather_than_success():
    """The bug this guards is subtle: with no recipients, neither delivery
    branch runs, so an `ok` flag left at its initial True would report SUCCESS
    for a message that was never sent -- and the operator would believe the
    alert went out."""
    n = Notifier(smtp_host="", smtp_user="", smtp_password="")
    assert n.configured is False
    assert n.send(_open_decision()) is False


def test_a_dead_carrier_gateway_is_called_out():
    """AT&T's gateway shut down in June 2025 and fails SILENTLY. Configuring
    one must not look like a working setup."""
    n = _notifier(sms_to=["5551234567@txt.att.net"])
    warnings = " ".join(n.configured_warnings())
    assert "silently go nowhere" in warnings
    assert "17 June 2025" in warnings


def test_a_sunsetting_gateway_is_flagged_but_not_condemned():
    n = _notifier(sms_to=["5551234567@vtext.com"])
    warnings = " ".join(n.configured_warnings())
    assert "still works today" in warnings
    assert "2027" in warnings


def test_sms_without_a_real_inbox_is_a_warning():
    """Carrier gateways do not bounce, so an SMS-only setup cannot tell you it
    has stopped working -- the 'configured, believed live, not running' trap."""
    n = Notifier(smtp_host="h", smtp_user="u", smtp_password="p",
                 sms_to=["5551234567@vtext.com"])
    assert any("cannot tell you it has stopped" in w
               for w in n.configured_warnings())


def test_a_clean_setup_has_no_warnings():
    assert _notifier().configured_warnings() == []


def test_dry_run_reports_success_without_sending():
    n = _notifier(sms_to=["5551234567@vtext.com"], dry_run=True)
    assert n.send(_open_decision()) is True


def test_a_forced_retraction_reaches_the_phone_even_though_shut_is_silent():
    """"shut" is normally never alerted and never texted. A retraction of an
    earlier "open" is the exception: it must get through on both legs."""
    n = _notifier(sms_to=["5551234567@vtext.com"], dry_run=True)
    shut = Decision(night="2026-10-05", route="shut",
                    reasons=["rain at 3:00am, while you would be asleep"])
    assert n.send(shut) is False              # unchanged night: stays quiet
    assert n.send(shut, force=True) is True   # retraction: goes out
