# weather-advice

Tells you, each evening, whether to open the windows for the night — and when
to expect to close them.

Watches the National Weather Service hourly forecast for one location, decides
whether there is a long enough stretch of cool, rain-free air between bedtime
and your alarm, and emails or texts you the answer. Records every night it
looks at, so the forecast's track record becomes a number rather than a memory.

**This belongs in its own repository, not in `mtga-advisor`.** It is here only
because that is the only repo this session could push to — creating a new one
was refused (`403 Resource not accessible by integration`). Nothing here
imports from `mtga-advisor`; this directory is a complete project root. To move
it, create an empty `weather-advice` repo and:

```bash
git clone https://github.com/LlamaAdam/mtga-advisor.git tmp
cd tmp && git checkout claude/zen-cori-051izr
git filter-repo --subdirectory-filter weather_advice   # or just copy the dir
git remote add origin https://github.com/LlamaAdam/weather-advice.git
git push -u origin master
```

Copying the directory into a fresh `git init` is fine too — there is only one
commit's worth of history to lose.

---

## The one idea everything follows from

> **The windows get opened once, in the evening, and closed when you wake up.**

Nobody gets up at 3am to shut a window. That single fact drives every rule:

* **Rain is judged over the whole night, not just the good part.** This is the
  trap, and it is worth spelling out. Suppose it is 72°F and clear from 11pm,
  rain starts at 5am, and your alarm is at 8am. A naive "find the longest
  comfortable run" finds six clean hours, says OPEN, and you wake at 8am to
  rain that blew through an open window for three hours. So once an open time
  is picked, `[open → alarm]` has to be dry end to end.

* **Temperature is not symmetrical with rain.** If it hits 80°F at 7am and the
  alarm is at 8am, that is one warm hour at the tail — annoying, survivable,
  and worth a sentence in the alert rather than cancelling the night. So
  temperature bounds the hours that get *counted*; rain vetoes the night.

* **A null chance-of-rain is "might rain", not zero.** NWS returns null on some
  grids and periods. "No data" is not "no rain" when the cost of being wrong is
  sleeping through a storm.

* **The wake time belongs to the morning, not the evening.** Friday at 11pm is
  followed by a *Saturday* morning, so Friday night gets the weekend's later
  alarm. Keying off the evening's weekday — the obvious mistake — makes Friday
  night end at 8am and Sunday night at 9am: both exactly backwards.

## Three verdicts

Borrowed from the deal tracker's routing, because the alert-fatigue problem is
the same one:

| Verdict | When | What happens |
|---|---|---|
| `open` | ≥ 6 hours of good air | Email **and** text |
| `marginal` | 3–6 hours | Email only — real, but a hassle |
| `shut` | under 3 hours, too warm, or any rain | Recorded, **never** alerted |
| `unknown` | the forecast could not be read | Recorded, so a dead run is visible |

A nightly "no" is how you teach yourself to ignore the channel, so there isn't
one. Under three hours you hear nothing at all.

**Retractions are the exception.** The check runs at 8pm, 9pm and 10pm, because
the forecast moves. Having been told "open them" at 8pm, the one message you
must not miss is the 10pm "actually, rain at 3am" — so a *changed* verdict
sends again, on both channels, even though `shut` is normally silent. An
unchanged verdict stays quiet.

---

## Try it right now

```bash
python -m pip install -r requirements.txt
python -m weather_advice preview --hours
```

`preview` reads and writes nothing, so it is safe to run repeatedly. `--hours`
prints the hour-by-hour forecast underneath the verdict so you can see the
decision being made.

Pretend it is a different evening:

```bash
python -m weather_advice preview --at 2026-10-05T20:00
```

Check the location is right before trusting anything:

```bash
python -m weather_advice resolve
```

That prints the city NWS matched for the configured coordinate, and verifies
the pinned station is one NWS actually serves for that grid cell. **Do this
first** — a wrong coordinate forecasts the next town over without ever looking
wrong, and a typo'd station identifier is indistinguishable from a station that
is down: both just produce no observations, quietly.

---

## Setting up the alerts

Preferences live in `config/weather_advice.yaml` and are safe to commit.
Secrets do not: copy `.env.example` to

```
../.secrets/weather-advice/.env
```

i.e. *outside* the project directory. The reasoning is lifted from
`mtgdeals/config.py`: `.gitignore` stops the honest mistake but does nothing
against `git add -f`, a zipped folder, a copied directory, or a tool that
ignores gitignore. Keeping the file where the repo cannot reach it makes the
accident unavailable.

Then:

```bash
python -m weather_advice doctor
```

`doctor` prints which config and secrets files were actually loaded, the
thresholds in force, and where alerts will go. It **exits non-zero** if there
is no working way to reach you.

### About texting yourself

This uses carrier email-to-SMS gateways (`5551234567@vtext.com`) through the
same SMTP path as the deal tracker. Be aware of what you are relying on:

| Carrier | Gateway | Status |
|---|---|---|
| T-Mobile | `@tmomail.net` | **Dead** since around December 2024 |
| AT&T | `@txt.att.net` | **Dead** since 17 June 2025 |
| Verizon | `@vtext.com` | Works today — hard sunset **31 March 2027** |

They **fail silently**: no bounce, no error, no acknowledgement. `doctor`
warns you if you configure a dead one, but it cannot detect a gateway that
accepts your mail and drops it.

So `WEATHER_ALERT_EMAIL_TO` — a real inbox — is the channel of record, and the
text is a convenience on top. Configuring SMS with no email address is a
warning, not a setup, because that arrangement cannot tell you it has stopped
working. That is the deal tracker's own lesson: it was once found
*"configured, believed live, and not running."*

If and when Verizon's gateway goes dark, the honest replacements are a push
service (ntfy is free, Pushover is a one-off $4.99) or real SMS through Twilio
(about $1.15/month plus a cent a message). `Notifier` is the only class that
would need to change.

---

## Running it nightly

```powershell
powershell -ExecutionPolicy Bypass -File deploy\install_windows_task.ps1
```

Registers a Scheduled Task that runs `check` at 8pm, 9pm and 10pm under
`pythonw.exe`, so no console window appears. It verifies the package imports
*and* runs `doctor` before scheduling anything, because a task that fails on
first launch looks identical to a task that was never registered.

It does not run while logged out — that would need a stored password.

There is deliberately **no** Startup-folder fallback, unlike the deal tracker's
installer. This is a *timed* job; a logon-triggered shortcut would check the
forecast at whatever hour you happened to sign in, which looks like it is
working and is not.

---

## The record

```bash
python -m weather_advice report
```

```
night        verdict   hours  window / reason
2026-09-24   open        9.0  22:00-07:00
2026-09-23   shut        2.0  22:00-00:00  (no alert)
2026-09-22   marginal    4.0  22:00-02:00
2026-09-21   shut        0.0  rain at 4:00am, while you would be asleep  (no alert)

tally: shut=2, open=2, marginal=1
forecast error: 2.0F mean absolute over 6 matched hours (worst 2.0F)
```

Three tables in `data/history.db`, because they answer three different
questions:

* `forecast_hour` — what the forecast *said*, keyed on `(fetched_at, start)`
  rather than `start`, so successive runs do not overwrite each other. That is
  the point: the interesting record is how a given hour's forecast **moved** as
  the night approached.
* `observation` — what actually happened, from **one pinned station**
  (`KADS`, Dallas/Addison Airport — the nearest reporting station).

  Pinning matters more than it looks. Accuracy is a comparison across time, and
  a comparison only means something if the thing being compared holds still.
  Left unpinned, the client takes whichever nearby station answers first, so a
  KADS outage silently swaps in an airport miles away and "forecast error"
  quietly starts measuring the distance between two stations instead of the
  quality of the forecast. For the same reason a pinned station deliberately
  does **not** fall back to another one: losing a few rows while it is down is
  recoverable, a history that mixes sources without saying so is not.
* `decision` — what was recommended, and whether an alert was delivered.

Accuracy joins the last forecast issued *before* each hour against the
observation nearest it. Grading against the latest-ever forecast would score it
on information it did not have, which flatters it.

Same principle as the deal tracker's note on sealed prices: *record price
history, so "near MSRP" is measured rather than eyeballed.* Here it makes "the
forecast said 74°F and it was 81°F" a number.

---

## Configuration worth knowing about

| Key | Default | Notes |
|---|---|---|
| `thresholds.max_temp_f` | `78` | "Below 78 or 77" — change this one number |
| `thresholds.min_temp_f` | `50` | Floor, so a 34°F January night is not a nine-hour "opportunity". `off` disables |
| `thresholds.max_precip_pct` | `20` | Conservative: you are asleep and cannot close them |
| `thresholds.max_dewpoint_f` | `off` | **Off on purpose.** Dallas is humid and 75°F at a 72°F dewpoint is muggy, but you asked for a temperature rule; a second rule that quietly blocks alerts would be answering a question nobody asked |
| `thresholds.target_hours` | `6` | Worth waking the phone for |
| `thresholds.min_hours` | `3` | Below this you hear nothing |
| `schedule.wake_weekend` | `09:00` | You said "9 or 10am"; 9 is the safe default, since assuming 10 would recommend a window that needs someone awake at 10 to close it |
| `location.station` | `KADS` | Dallas/Addison Airport. Blank it to use the nearest available, at the cost of a mixed accuracy history |

> One gotcha, since it cost a bug already: in YAML the bare word `off` parses as
> the boolean `false`, and `float(false)` is `0.0` — which would mean "only open
> when the dewpoint is below 0°F" and veto every night, silently. `_opt_float`
> handles it and `tests/test_config.py` keeps it handled. Use `off`, not `0`, to
> disable a threshold.

---

## Tests

```bash
python -m pytest
```

58 tests, entirely offline — no network, matching how `mtga-advisor` and
`mtgdeals` both test. Most encode a specific way of being wrong; the ones worth
reading are `test_rain_at_5am_cancels_the_night_even_though_six_clean_hours_exist`,
`test_friday_night_gets_the_weekend_wake_time`, and
`test_yaml_off_disables_a_threshold_rather_than_setting_it_to_zero`.

## Limits

* **US only.** api.weather.gov does not cover anywhere else.
* **One location, one station.** No reason it could not take several; nothing
  needs it yet.
* **Not verified against the live API.** It was built where
  `api.weather.gov` is unreachable, so the parsing is tested against captured
  fixtures rather than a real response. `preview` on a real machine is the
  first thing to run, and the first place a shape mismatch would show up.
* **No humidity rule by default.** See the table above — deliberate, not an
  oversight.
