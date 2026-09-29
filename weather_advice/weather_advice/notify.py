"""Alert delivery: real email, plus SMS through a carrier email-to-SMS gateway.

Adapted from `mtgdeals/notify_email.py`, which is the operator's existing and
working alert path, so the shape here is deliberately familiar.

*** READ THIS BEFORE TRUSTING THE SMS LEG ***

Carrier email-to-SMS gateways are being switched off, and the ones still alive
FAIL SILENTLY -- no bounce, no error, no acknowledgement:

    T-Mobile  @tmomail.net   dead since around December 2024
    AT&T      @txt.att.net   dead since 17 June 2025
    Verizon   @vtext.com     still partly working; hard sunset 31 March 2027

A silent failure is the worst possible outcome for this program. The deal
tracker's README records the lesson in its own words -- that system was found
"CONFIGURED, BELIEVED LIVE, AND NOT RUNNING" -- and an SMS gateway that
accepts your mail and drops it reproduces exactly that, except you only find
out on the night you wanted the window open.

So: `email_to` is the channel of record and SMS is a convenience on top. When
an SMS address is configured with no email address, that is a warning, not a
setup -- `configured_warnings()` says so and the CLI prints it. Both legs are
attempted and reported independently, because "the text did not arrive" and
"nothing was sent" need different fixes.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import List, Optional, Sequence

from .models import Decision

log = logging.getLogger(__name__)

# Anything longer is unreadable on a lock screen, and carriers segment at 160.
SMS_LIMIT = 300

# Gateways known to be switched off. Configuring one is a silent no-op, so it
# is worth saying out loud rather than letting the mail vanish.
DEAD_GATEWAYS = {
    "tmomail.net": "T-Mobile's gateway shut down around December 2024",
    "txt.att.net": "AT&T's gateway shut down 17 June 2025",
    "mms.att.net": "AT&T's MMS gateway shut down 17 June 2025",
}
SUNSETTING_GATEWAYS = {
    "vtext.com": "Verizon has announced a hard sunset on 31 March 2027",
    "vzwpix.com": "Verizon has announced a hard sunset on 31 March 2027",
}


def _fmt(dt) -> str:
    """12-hour clock, no leading zero, portable (see windows._fmt)."""
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt.minute:02d}{'am' if dt.hour < 12 else 'pm'}"


@dataclass
class Notifier:
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: Sequence[str] = field(default_factory=list)
    sms_to: Sequence[str] = field(default_factory=list)
    # Which verdicts are worth a message. "shut" is never alerted -- a nightly
    # "no" is how you teach yourself to ignore the channel.
    routes: Sequence[str] = ("open", "marginal")
    # A marginal night is real but a hassle. Default it to email only, so the
    # phone buzzes for the nights actually worth acting on.
    sms_routes: Sequence[str] = ("open",)
    dry_run: bool = False
    timeout: int = 20

    def __post_init__(self) -> None:
        self.email_to = [a for a in (self.email_to or []) if a]
        self.sms_to = [a for a in (self.sms_to or []) if a]
        self.smtp_port = int(self.smtp_port or 587)

    @property
    def configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password
                    and (self.email_to or self.sms_to))

    def handles(self, route: str) -> bool:
        return route in self.routes

    def configured_warnings(self) -> List[str]:
        """Setup problems worth printing before they cost a night's sleep."""
        out: List[str] = []
        for addr in self.sms_to:
            domain = addr.split("@")[-1].lower().strip()
            if domain in DEAD_GATEWAYS:
                out.append(
                    f"{addr} will silently go nowhere: {DEAD_GATEWAYS[domain]}. "
                    "Set WEATHER_ALERT_EMAIL_TO to a real inbox instead.")
            elif domain in SUNSETTING_GATEWAYS:
                out.append(
                    f"{addr} still works today, but {SUNSETTING_GATEWAYS[domain]} "
                    "-- keep a real email address configured as the fallback.")
        if self.sms_to and not self.email_to:
            out.append(
                "SMS is configured with no email address. Carrier gateways fail "
                "silently, so this setup cannot tell you it has stopped working.")
        return out

    # -- formatting ---------------------------------------------------------

    @staticmethod
    def subject_for(d: Decision) -> str:
        """Front-load the answer. A phone shows roughly 40 characters, so the
        verdict and the hours must land before the cutoff."""
        if d.route == "open" and d.open_at and d.close_at:
            return (f"[windows] Open tonight {_fmt(d.open_at)}-"
                    f"{_fmt(d.close_at)} ({d.hours:.0f}h)")
        if d.route == "marginal" and d.open_at and d.close_at:
            return (f"[windows] Marginal: only {d.hours:.1f}h "
                    f"({_fmt(d.open_at)}-{_fmt(d.close_at)})")
        if d.route == "unknown":
            return "[windows] Forecast unavailable tonight"
        return "[windows] Keep them shut tonight"

    @staticmethod
    def body_for(d: Decision) -> str:
        lines: List[str] = []
        if d.open_at and d.close_at:
            lines.append(f"Open   {_fmt(d.open_at)}")
            lines.append(f"Close  {_fmt(d.close_at)}  ({d.hours:.1f} hours)")
        if d.low_f is not None and d.high_f is not None:
            lines.append(f"Temp   {d.low_f:.0f}-{d.high_f:.0f}F while open")
        if d.wake_at:
            lines.append(f"Alarm  {_fmt(d.wake_at)}")
        if d.warm_after:
            lines.append("")
            lines.append(f"Climbs past the limit after {_fmt(d.warm_after)}; "
                         "expect the last stretch to be warm.")
        if d.reasons:
            lines.append("")
            lines.extend(f"  - {r}" for r in d.reasons)
        lines.append("")
        lines.append(f"night: {d.night}")
        return "\n".join(lines)

    @staticmethod
    def sms_for(d: Decision) -> str:
        """Readable on a lock screen without unlocking it."""
        if d.open_at and d.close_at:
            head = "Open windows" if d.route == "open" else "Marginal"
            text = (f"{head} {_fmt(d.open_at)}-{_fmt(d.close_at)} "
                    f"({d.hours:.1f}h")
            if d.low_f is not None and d.high_f is not None:
                text += f", {d.low_f:.0f}-{d.high_f:.0f}F"
            text += ")"
            if d.warm_after:
                text += f" warm after {_fmt(d.warm_after)}"
            return text[:SMS_LIMIT]
        reason = d.reasons[0] if d.reasons else "no good window"
        return f"Keep windows shut: {reason}"[:SMS_LIMIT]

    # -- delivery -----------------------------------------------------------

    def send(self, d: Decision, force: bool = False) -> bool:
        """True only if every configured leg was delivered.

        The `configured` check comes BEFORE the legs deliberately: an
        unconfigured notifier that ran neither branch would otherwise leave
        `ok` at its initial True and report success for a message it never
        sent -- the same bug called out in the deal tracker's notify_email.
        """
        # `force` carries a revision through: a night that turned from OPEN
        # to SHUT is normally an unalerted route, but the retraction is the
        # whole point of noticing the change.
        if not force and not self.handles(d.route):
            return False
        if not self.configured:
            log.warning("notifier not configured; %s alert not sent", d.route)
            return False

        ok = True
        if self.email_to:
            ok = self._deliver(list(self.email_to), self.subject_for(d),
                               self.body_for(d)) and ok
        if self.sms_to and (force or d.route in self.sms_routes):
            # Gateways put the SUBJECT in the message on some networks and the
            # BODY on others, so send an empty subject and keep it all in body.
            ok = self._deliver(list(self.sms_to), "", self.sms_for(d)) and ok
        return ok

    def _deliver(self, recipients: List[str], subject: str, body: str) -> bool:
        if self.dry_run:
            log.info("[dry-run] would send to %s: %s",
                     ", ".join(recipients), subject or body[:70])
            return True
        try:
            msg = EmailMessage()
            msg["From"] = self.smtp_user
            msg["To"] = ", ".join(recipients)
            # email.policy refuses CR/LF in a header; flatten whitespace and
            # build the message INSIDE the try so a malformed subject can
            # never take down the run.
            msg["Subject"] = " ".join((subject or "").split())
            msg.set_content(body)
            context = ssl.create_default_context()
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port,
                                      timeout=self.timeout, context=context) as s:
                    s.login(self.smtp_user, self.smtp_password)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port,
                                  timeout=self.timeout) as s:
                    s.starttls(context=context)
                    s.login(self.smtp_user, self.smtp_password)
                    s.send_message(msg)
            return True
        except Exception as exc:                      # noqa: BLE001
            # Never let delivery take down the run; the decision is still
            # recorded to history either way.
            log.warning("delivery to %s failed: %s", ", ".join(recipients), exc)
            return False
