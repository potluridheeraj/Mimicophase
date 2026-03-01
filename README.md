
# Mimicophase Local (Classic Mimicophase Variant)

This repository now contains a **fully local-network playable prototype** inspired by Jackbox-style host/player flow:

- A host starts one room from a laptop/desktop.
- Players join from any browser/device on the same network.
- Session stickiness is supported via browser local storage (refresh/reopen retains identity token).
- Host can reorder players in a **seating circle** in lobby so adjacency-based effects are deterministic.
- Rejoin endpoint restores users to the same stage/room if they come back.
- Players can view/copy their reconnect token in the player page for manual rejoin if local storage is cleared.
- Disconnected players are temporarily excluded from active voting/action counts until they reconnect.
- Host can kick disconnected/stalled players and reset a game mid-match if needed.
- Host can configure phase timers before start; voting phases auto-complete early when all connected players submit votes.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open:
- Host: `http://<host-lan-ip>:8000/host`
- Players: `http://<host-lan-ip>:8000/play`

## Test

```bash
pytest -q
```

---

## Gameplay Specification (Canonical Rules)

# Mimicophase (Classic Mimicophase Variant) — Core Rules & Gameplay Details

This is the **game-only** specification (no system design, architecture, deployment, or UI).

This is a sci-fi reskin of the Classic Mimicophase (Custom Variant).
**Story premise:** After investigating a planet, everyone returns to their base and realizes that **one or more crew members have become Mimicophase**. From that moment on, the game proceeds in repeating phases as the Crew tries to identify and eliminate the Mimicophase before they take over.

---

## Objective

- **Crew win** if **all Mimicophase are eliminated**.
- **Mimicophase win** if the **number of Mimicophase is equal to or greater than** the number of Crew.

---

## Turn Flow (Loop)

1. **Night Phase** — Mimicophase act, Captains act, Doctor protects (in order).
2. **Morning Phase** — Moderator announces deaths (names only).
3. **Day Discussion** — All living players may talk freely.
4. **Voting Phase** — Players nominate and execute one player.
5. Repeat until a win condition is met.

---

## Roles

### Mimicophase
- Each night, Mimicophase choose **one living non-Mimicophase** player to kill.
- **Unanimous pick required** among all living Mimicophase.
- If Mimicophase disagree, they must continue discussing/changing picks **until unanimous**.

### Captains
- Each night, Captains collectively choose **one living player** to inspect.
- **Unanimous pick required** among all living Captains.
- **Effect rule:** If the final unanimous target is a **Mimicophase**, that Mimicophase is **marked for death** (subject to Doctor protection).
- Captains are **not told** the inspected player’s role; any effect appears only via Morning deaths.

### Doctor
- Each night, the Doctor chooses **one living player** (including self) to protect.
- The Doctor has **no knowledge** of:
  - who Mimicophase targeted,
  - who Captains inspected,
  - whether protection “worked,”
  - or who died (until Morning).

### Crew
- No night action.

---

## Night Phase Order (Strict)

1. **Mimicophase** choose and confirm a target (**must be unanimous**).
2. **Captains** choose and confirm a target (**must be unanimous**).
3. **Doctor** chooses one player to protect.
4. **Moderator** resolves outcomes using the truth table below.

> **Important:** If Mimicophase/Captains do not reach unanimity before any timer ends, **the timer is ignored** and the selection continues until unanimity is achieved.

---

## Resolution Rules

### Truth Table — Target Outcomes

Legend:
- **MT** = Mimicophase Target (Mimicophase selected the player)
- **CM** = Captain Marked (Captains unanimously targeted a player who is actually a Mimicophase)
- **DP** = Doctor Protected
- **Outcome** = Final result after resolution

| MT | CM | DP | Outcome |
|---:|---:|---:|---|
| Y | N | N | Killed by Mimicophase |
| Y | N | Y | Survives (protected) |
| N | Y | N | Killed by Captains (announced next Morning) |
| N | Y | Y | Survives (protected) |
| Y | Y | N | Killed (both effects apply) |
| Y | Y | Y | Survives (protected) |
| N | N | N | Survives |

### Resolution Order (Moderator)

1. Apply **Doctor protection** to the protected player.
2. Eliminate the **Mimicophase target** unless protected.
3. Eliminate the **Captain-marked Mimicophase** unless protected.

---

## Morning Phase

- Moderator announces the **names** of players eliminated overnight.
- **No cause is ever revealed** (not “Mimicophase” vs “Captain mark” vs “both”).
- If nobody died, announce **“No deaths.”**
- If two players died, announce both names (order is not meaningful).

---

## Day Discussion

- All living players may discuss freely to deduce roles and plan votes.
- No enforced structure beyond the timer (if used).

---

## Voting Phase

### Nomination Collection
- Any living player may nominate any living player.

### If there are **2+ nominees**
1. Identify the **Top 2** by nomination votes.
2. Those two give justification.
3. All living players vote between the Top 2.
4. **Tie → immediate re-vote**, repeated until a majority is reached.

### If there is **exactly 1 nominee**
1. The nominee gives justification.
2. All living players vote:
   - **Execute** the nominee, or
   - **Reject** and return to nominations.
3. If majority votes execute → nominee is eliminated.
4. Otherwise → restart nomination collection.

### Tie Handling (No Randomness)
- **Nomination ties:** If there’s a tie for second place, include **all** tied players in the runoff.
- **Execution vote ties:** re-vote repeatedly until **one option has a majority**.
- **No coin flips / no random elimination** at any point.

---

## Victory Conditions (Checked After Morning and After Execution)

- **Crew win immediately** when **all Mimicophase are dead**.
- **Mimicophase win immediately** when **Mimicophase ≥ Crew**.

---

## Optional Rules (Gameplay-Level)

These are optional *social/illusion* rules; they do not change the core resolution logic unless stated.

- **Announce Mimicophase alive at Night:** Moderator announces the count of living Mimicophase (number only).
- **Announce Captains alive at Night:** Moderator announces the count of living Captains (number only).
- **Phantom calls:** Moderator still “calls” Captains/Doctor to act even if they are dead, to hide role deaths.

---

## Edge Cases

1. **Doctor can protect self:** allowed.
2. **Targeting a dead player is invalid:** Mimicophase/Captains must re-select a living valid target.
3. **Mimicophase must target a non-Mimicophase:** if a Mimicophase target list includes a Mimicophase due to a bug, the selection must be rejected as invalid.
4. **Unanimity overrides timers:** Mimicophase/Captains phases do not end until unanimity is reached.
5. **Captain inspects a non-Mimicophase:** no effect (no mark).
6. **Doctor protection applies to all deaths:** protects against Mimicophase kills and Captain marks equally.

---

## Scenarios (QA Walkthroughs)

### Scenario 1 — Standard 8-Player Game
**Setup:** 8 players: 2 Mimicophase, 1 Captain, 1 Doctor, 4 Crew.

**Night 1**
- Mimicophase choose Player D.
- Captain inspects Player F (Crew Member → no effect).
- Doctor protects Player D → Player D survives.

**Morning 1**
- No deaths announced.

**Day 1**
- Discussion.
- Voting executes Crew Member E.

---

### Scenario 2 — Mimicophase Disagree (Unanimity Loop)
**Setup:** 3 Mimicophase alive.

**Night**
- W1 picks A, W2 picks B, W3 picks B.
- Mimicophase must continue discussing/changing picks until all confirm **B**.
- Night proceeds only after unanimous lock.

---

### Scenario 3 — Captains Disagree (Unanimity Loop)
**Setup:** 2 Captains alive.

**Night**
- S1 picks X, S2 picks Y.
- Captains must align and confirm the **same** target before the night can proceed.

---

### Scenario 4 — Doctor Protects Self
**Setup:** Doctor is targeted by Mimicophase.

**Night**
- Mimicophase unanimously target Doctor.
- Doctor protects self.

**Morning**
- Doctor survives (protected).

---

### Scenario 5 — No-Death Night
**Setup:**
- Mimicophase target Player A.
- Doctor protects Player A.
- Captains target Player B (Crew Member).

**Morning**
- No deaths announced.

---

### Scenario 6 — Two Deaths in One Night
**Setup:**
- Mimicophase target Player M.
- Captains unanimously target a Mimicophase (Player Z).
- Doctor protects Player M.

**Morning**
- Player Z dies (Captain mark).
- Player M survives (protected).
- Morning announces: **“Z.”**

> Note: Only names are announced; the group never learns *why*.

---

### Scenario 7 — Voting Tie Repeat
**Setup:** 6 alive, final vote between A and B.

- Vote 1: 3–3 tie → re-vote.
- Vote 2: 3–3 tie → re-vote.
- Continue until one reaches majority.

---

### Scenario 8 — Dead Player Target Attempt
**Setup:** UI lag shows a dead player as selectable.

**Rule:**
- The system/moderator must reject it as invalid.
- Mimicophase/Captains must choose a **living** valid target.

---

### Scenario 9 — All Captains Dead (Phantom Calls)
**Setup:** No Captains remain.

**Rule:**
- Moderator may still “call” Captains during Night to preserve uncertainty.
- No Captain action occurs.

---

### Scenario 10 — Early Win
- If all Mimicophase are eliminated at any point → **Crew win immediately**.
- If Mimicophase ≥ Crew at any point → **Mimicophase win immediately**.

---

## Full Match Walkthrough (Example: 12 Players, 2 Nights)

> This example is **canonical** only until a win condition is met.

**Setup (12 players)**
- Mimicophase: M1, M2, M3
- Captains: C1, C2
- Doctor: D
- Crew: R1–R6
- Reveal at death: HIDDEN
- Announce Mimicophase alive: ON
- Announce Captains alive: OFF
- Phantom calls: ON

### Cycle 1
**Night 1**
- Mimicophase eventually agree to target **R3**.
- Captains agree to inspect **M2** (Mimicophase → marked for death).
- Doctor protects **R3**.

**Morning**
- Announce: **M2** (only name; no cause).

**Day + Voting**
- Runoff vote executes **R2**.

**Win check**
- Mimicophase alive: 2 → game continues.

### Cycle 2
**Night 2**
- Mimicophase agree to target **C1**.
- Captains agree to inspect **M1** (Mimicophase → marked for death).
- Doctor protects **C1**.

**Morning**
- Announce: **M1**.

**Day + Voting**
- Runoff vote executes **M3**.

**Win check**
- Mimicophase alive: 0 → **Crew win immediately**.

---

## Expansion Note — More Characters Coming

This is **Volume 1** of the gameplay spec for the Mimicophase variant. Additional characters/roles (and optional modules) will be introduced in later volumes, but they will be designed to **preserve the core phase loop and resolution logic** defined here unless explicitly stated.

## Notes (Interpretation Rules)

- Morning announcements list **names only**, never causes.
- Unanimity is strict for Mimicophase and Captains; Doctor is single-choice.
- Protection applies equally to Mimicophase kills and Captain marks.
- Voting never uses randomness: re-vote until majority.
