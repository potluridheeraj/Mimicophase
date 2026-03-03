from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import random
import time


class Role(str, Enum):
    MIMICOPHASE = "mimicophase"
    CAPTAIN = "captain"
    DOCTOR = "doctor"
    CREW = "crew"


class Phase(str, Enum):
    LOBBY = "lobby"
    NIGHT_MIMIC = "night_mimic"
    NIGHT_CAPTAIN = "night_captain"
    NIGHT_DOCTOR = "night_doctor"
    MORNING = "morning"
    DISCUSSION = "discussion"
    NOMINATION = "nomination"
    RUNOFF = "runoff"
    SINGLE_NOMINEE = "single_nominee"
    ENDED = "ended"


@dataclass
class Player:
    id: str
    name: str
    token: str
    alive: bool = True
    role: Optional[Role] = None
    connected: bool = True
    kicked: bool = False
    seat: Optional[int] = None


@dataclass
class NightActions:
    mimic_choice: Optional[str] = None
    captain_choice: Optional[str] = None
    doctor_choice: Optional[str] = None
    mimic_votes: Dict[str, str] = field(default_factory=dict)
    captain_votes: Dict[str, str] = field(default_factory=dict)


@dataclass
class GameRoom:
    code: str
    host_token: str
    players: Dict[str, Player] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    phase: Phase = Phase.LOBBY
    cycle: int = 0
    winner: Optional[str] = None
    night_actions: NightActions = field(default_factory=NightActions)
    morning_deaths: List[str] = field(default_factory=list)
    nominations: Dict[str, Set[str]] = field(default_factory=dict)
    runoff_candidates: List[str] = field(default_factory=list)
    runoff_votes: Dict[str, str] = field(default_factory=dict)
    phase_durations: Dict[Phase, int] = field(default_factory=lambda: {
        Phase.MORNING: 15,
        Phase.DISCUSSION: 90,
        Phase.NOMINATION: 45,
        Phase.RUNOFF: 45,
        Phase.SINGLE_NOMINEE: 45,
    })
    phase_deadline: Optional[float] = None

    def add_player(self, player: Player) -> None:
        self.players[player.id] = player
        self.order.append(player.id)
        self._normalize_seats()

    def living_player_ids(self) -> List[str]:
        return [pid for pid in self.order if self.players[pid].alive and not self.players[pid].kicked]

    def active_living_player_ids(self) -> List[str]:
        return [pid for pid in self.living_player_ids() if self.players[pid].connected]

    def _normalize_seats(self) -> None:
        for idx, pid in enumerate(self.order):
            self.players[pid].seat = idx

    def reorder_by_seats(self, ordered_ids: List[str]) -> None:
        if set(ordered_ids) != set(self.order):
            raise ValueError("Seat order must include all players exactly once")
        self.order = ordered_ids
        self._normalize_seats()

    def adjacent_players(self, player_id: str, alive_only: bool = True) -> List[str]:
        pool = self.living_player_ids() if alive_only else [pid for pid in self.order if not self.players[pid].kicked]
        if player_id not in pool or len(pool) < 2:
            return []
        idx = pool.index(player_id)
        left = pool[(idx - 1) % len(pool)]
        right = pool[(idx + 1) % len(pool)]
        return [left] if left == right else [left, right]

    def assign_roles(self) -> None:
        pids = [pid for pid in self.order if not self.players[pid].kicked]
        n = len(pids)
        if n < 5:
            raise ValueError("Need at least 5 players")
        mimic_count = max(1, n // 4)
        captain_count = 1 if n < 9 else 2

        shuffled = pids[:]
        random.shuffle(shuffled)
        mimic_ids = set(shuffled[:mimic_count])
        captain_ids = set(shuffled[mimic_count:mimic_count + captain_count])
        doctor_id = shuffled[mimic_count + captain_count]

        for pid in pids:
            if pid in mimic_ids:
                self.players[pid].role = Role.MIMICOPHASE
            elif pid in captain_ids:
                self.players[pid].role = Role.CAPTAIN
            elif pid == doctor_id:
                self.players[pid].role = Role.DOCTOR
            else:
                self.players[pid].role = Role.CREW

        self.phase = Phase.NIGHT_MIMIC
        self.cycle = 1
        self.phase_deadline = None

    def alive_by_role(self, role: Role, active_only: bool = True) -> List[str]:
        return [
            p.id
            for p in self.players.values()
            if p.alive and not p.kicked and (not active_only or p.connected) and p.role == role
        ]

    def check_victory(self) -> Optional[str]:
        mimic_alive = len(self.alive_by_role(Role.MIMICOPHASE, active_only=True))
        crew_alive = len([
            p.id for p in self.players.values()
            if p.alive and not p.kicked and p.connected and p.role != Role.MIMICOPHASE
        ])
        if mimic_alive == 0:
            self.winner = "crew"
        elif mimic_alive >= crew_alive and crew_alive > 0:
            self.winner = "mimicophase"
        if self.winner:
            self.phase = Phase.ENDED
            self.phase_deadline = None
        return self.winner

    def set_unanimous_action(self, role: Role, target_id: str, actor_id: Optional[str] = None) -> None:
        if target_id not in self.players or not self.players[target_id].alive or self.players[target_id].kicked:
            raise ValueError("Target must be a living player")

        if role == Role.MIMICOPHASE:
            if self.players[target_id].role == Role.MIMICOPHASE:
                raise ValueError("Mimicophase must target non-Mimicophase")
            if actor_id is None:
                self.night_actions.mimic_choice = target_id
                self.phase = Phase.NIGHT_CAPTAIN
                return
            self._record_unanimous_vote(Role.MIMICOPHASE, actor_id, target_id)
        elif role == Role.CAPTAIN:
            if actor_id is None:
                self.night_actions.captain_choice = target_id
                self.phase = Phase.NIGHT_DOCTOR
                return
            self._record_unanimous_vote(Role.CAPTAIN, actor_id, target_id)
        else:
            raise ValueError("Invalid unanimous action role")

    def _record_unanimous_vote(self, role: Role, actor_id: str, target_id: str) -> None:
        if actor_id not in self.players:
            raise ValueError("Unknown actor")
        actor = self.players[actor_id]
        if actor.role != role or not actor.alive or actor.kicked or not actor.connected:
            raise ValueError("Only connected living players in role can vote")

        voters = sorted(self.alive_by_role(role, active_only=True))
        if not voters:
            raise ValueError("No eligible voters")

        if role == Role.MIMICOPHASE:
            votes = self.night_actions.mimic_votes
            next_phase = Phase.NIGHT_CAPTAIN
            choice_attr = "mimic_choice"
        else:
            votes = self.night_actions.captain_votes
            next_phase = Phase.NIGHT_DOCTOR
            choice_attr = "captain_choice"

        votes[actor_id] = target_id
        if len(votes) != len(voters):
            return

        selections = {votes[pid] for pid in voters}
        if len(selections) != 1:
            return

        setattr(self.night_actions, choice_attr, target_id)
        votes.clear()
        self.phase = next_phase

    def set_doctor_action(self, target_id: str) -> None:
        if target_id not in self.players or not self.players[target_id].alive or self.players[target_id].kicked:
            raise ValueError("Target must be a living player")
        self.night_actions.doctor_choice = target_id
        self.resolve_night()

    def resolve_night(self) -> None:
        mimic_target = self.night_actions.mimic_choice
        captain_target = self.night_actions.captain_choice
        doctor_target = self.night_actions.doctor_choice
        deaths: Set[str] = set()

        captain_marked: Optional[str] = None
        if captain_target and self.players[captain_target].role == Role.MIMICOPHASE:
            captain_marked = captain_target

        if mimic_target and mimic_target != doctor_target:
            deaths.add(mimic_target)
        if captain_marked and captain_marked != doctor_target:
            deaths.add(captain_marked)

        for pid in deaths:
            self.players[pid].alive = False

        self.morning_deaths = list(deaths)
        self.night_actions = NightActions()
        if self.check_victory():
            return
        self.phase = Phase.MORNING
        self._set_deadline_for_phase()

    def _set_deadline_for_phase(self) -> None:
        duration = self.phase_durations.get(self.phase)
        self.phase_deadline = time.time() + duration if duration else None

    def set_phase_durations(self, morning_s: int, discussion_s: int, nomination_s: int, runoff_s: int) -> None:
        self.phase_durations[Phase.MORNING] = max(5, morning_s)
        self.phase_durations[Phase.DISCUSSION] = max(10, discussion_s)
        self.phase_durations[Phase.NOMINATION] = max(10, nomination_s)
        self.phase_durations[Phase.RUNOFF] = max(10, runoff_s)
        self.phase_durations[Phase.SINGLE_NOMINEE] = max(10, runoff_s)

    def tick(self) -> None:
        if not self.phase_deadline or self.phase in (Phase.ENDED, Phase.LOBBY):
            return
        if time.time() < self.phase_deadline:
            return
        if self.phase in (Phase.MORNING, Phase.DISCUSSION):
            self.advance_day()
        elif self.phase == Phase.NOMINATION:
            if self.nominations:
                self.finalize_nominations()
            else:
                self._set_deadline_for_phase()
        elif self.phase in (Phase.RUNOFF, Phase.SINGLE_NOMINEE):
            # only finalize if all active living players voted
            if len(self.runoff_votes) >= len(self.active_living_player_ids()):
                self.finalize_runoff()
            else:
                self._set_deadline_for_phase()

    def advance_day(self) -> None:
        if self.phase == Phase.MORNING:
            self.phase = Phase.DISCUSSION
            self._set_deadline_for_phase()
        elif self.phase == Phase.DISCUSSION:
            self.phase = Phase.NOMINATION
            self.nominations = {}
            self._set_deadline_for_phase()

    def submit_nomination(self, voter_id: str, nominee_id: str) -> None:
        if self.phase != Phase.NOMINATION:
            raise ValueError("Not nomination phase")
        if not self.players[voter_id].alive or not self.players[nominee_id].alive:
            raise ValueError("Only living players participate")
        if not self.players[voter_id].connected or self.players[voter_id].kicked:
            raise ValueError("Only connected players can nominate")
        self.nominations.setdefault(nominee_id, set()).add(voter_id)

    def finalize_nominations(self) -> None:
        if not self.nominations:
            raise ValueError("No nominations")
        ranked = sorted(self.nominations.items(), key=lambda kv: len(kv[1]), reverse=True)
        if len(ranked) == 1:
            self.runoff_candidates = [ranked[0][0]]
            self.phase = Phase.SINGLE_NOMINEE
            self.runoff_votes = {}
            self._set_deadline_for_phase()
            return

        second_votes = len(ranked[1][1])
        top_votes = len(ranked[0][1])
        candidates = [nom for nom, voters in ranked if len(voters) == top_votes]
        if len(candidates) < 2:
            candidates.append(ranked[1][0])
            candidates.extend([nom for nom, voters in ranked[2:] if len(voters) == second_votes])

        seen = set()
        self.runoff_candidates = [c for c in candidates if not (c in seen or seen.add(c))]
        self.phase = Phase.RUNOFF
        self.runoff_votes = {}
        self._set_deadline_for_phase()

    def submit_runoff_vote(self, voter_id: str, choice: str) -> None:
        if self.phase not in (Phase.RUNOFF, Phase.SINGLE_NOMINEE):
            raise ValueError("Not runoff phase")
        if not self.players[voter_id].alive or not self.players[voter_id].connected or self.players[voter_id].kicked:
            raise ValueError("Only connected living players can vote")

        valid_choices = self.runoff_candidates[:] if self.phase == Phase.RUNOFF else ["execute", "reject"]
        if choice not in valid_choices:
            raise ValueError("Invalid choice")
        self.runoff_votes[voter_id] = choice

    def finalize_runoff(self) -> Optional[str]:
        living = self.active_living_player_ids()
        if len(self.runoff_votes) < len(living):
            raise ValueError("All connected living players must vote")

        counts: Dict[str, int] = {}
        for v in self.runoff_votes.values():
            counts[v] = counts.get(v, 0) + 1
        threshold = len(living) // 2 + 1

        if self.phase == Phase.SINGLE_NOMINEE:
            if counts.get("execute", 0) >= threshold:
                eliminated = self.runoff_candidates[0]
                self.players[eliminated].alive = False
                if self.check_victory():
                    return eliminated
                self.start_next_night()
                return eliminated
            self.phase = Phase.NOMINATION
            self.nominations = {}
            self.runoff_votes = {}
            self._set_deadline_for_phase()
            return None

        winners = [c for c, n in counts.items() if n >= threshold]
        if len(winners) != 1:
            self.runoff_votes = {}
            self._set_deadline_for_phase()
            return None
        eliminated = winners[0]
        self.players[eliminated].alive = False
        if self.check_victory():
            return eliminated
        self.start_next_night()
        return eliminated

    def start_next_night(self) -> None:
        self.cycle += 1
        self.phase = Phase.NIGHT_MIMIC
        self.nominations = {}
        self.runoff_votes = {}
        self.runoff_candidates = []
        self.morning_deaths = []
        self.phase_deadline = None

    def reset_game(self) -> None:
        self.phase = Phase.LOBBY
        self.cycle = 0
        self.winner = None
        self.phase_deadline = None
        self.night_actions = NightActions()
        self.morning_deaths = []
        self.nominations = {}
        self.runoff_candidates = []
        self.runoff_votes = {}
        for p in self.players.values():
            if p.kicked:
                continue
            p.alive = True
            p.role = None

    def kick_player(self, player_id: str) -> None:
        if player_id not in self.players:
            raise ValueError("Unknown player")
        p = self.players[player_id]
        p.connected = False
        p.kicked = True
        p.alive = False
        self.nominations.pop(player_id, None)
        self.runoff_candidates = [c for c in self.runoff_candidates if c != player_id]
        self.runoff_votes.pop(player_id, None)
        for voters in self.nominations.values():
            voters.discard(player_id)
        self.check_victory()
