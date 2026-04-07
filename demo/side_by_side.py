"""
side_by_side.py — Split-screen demo: FCFS Baseline (left) vs. Trained Agent (right).

Both instances run on IDENTICAL schedules starting from t=0 with identical RNG
seeds.  The only difference is the dispatching policy.  Same inputs → different
outcomes → that's the whole story.

Usage:
    python -m demo.side_by_side \\
        --checkpoint checkpoints/latest.zip \\
        --scenario   demo/scenarios/medium.json \\
        [--speed     60]          # sim-seconds per wall-second (default 60)
        [--fps       30]          # display FPS (default 30)
        [--record    demo.mp4]    # optional mp4 output
        [--seed      0]           # RNG seed for any stochastic elements

Controls:
    SPACE   — pause / resume live run
    ← / →   — step backward / forward one frame (while paused or in replay)
    ESC     — quit
"""

from __future__ import annotations

import argparse
import copy
import sys
import time
from pathlib import Path

import pygame

# ── Local imports ─────────────────────────────────────────────────────────────

from sim.world import build_taxiway_graph, build_gates, build_runways, NODE_POSITIONS
from sim.scheduler import load_schedule
from sim.dispatcher import Dispatcher
from sim.entities import (
    AircraftState, VehicleState,
    FuelTruck, BaggageTug, PushbackTractor,
    Aircraft, Vehicle,
)
from env.airport_env import (
    AirportEnv, RLDispatcher, _build_fleet,
    ACTION_HOLD, SIM_HORIZON,
)
from demo.scoreboard import draw_scoreboard
from demo.replay import ReplayRecorder, ReplayController, proxies_from_snapshot

# ── Layout constants ──────────────────────────────────────────────────────────

SCORE_H  = 190           # scoreboard height (px)
PANEL_W  = 780           # width of each sim panel
PANEL_H  = 520           # height of each sim panel
WINDOW_W = PANEL_W * 2  # 1560
WINDOW_H = SCORE_H + PANEL_H  # 710

# Scale from original 1200×700 sim canvas
SCALE_X  = PANEL_W / 1200.0   # ≈ 0.65
SCALE_Y  = PANEL_H / 700.0    # ≈ 0.743

# ── Colour palette (panel renderer) ──────────────────────────────────────────

BG_COLOR       = (15,  18,  28)
TAXIWAY_COLOR  = (70,  70,  85)
TAXIWAY_OCC    = (160, 70,  70)
GATE_COLOR     = (50,  195, 200)
RUNWAY_COLOR   = (50,  150,  50)
AC_COLOR       = (255, 220,  50)
AC_HOLD_COLOR  = (255, 100,  50)
FUEL_COLOR     = (220,  60,  60)
BAGGAGE_COLOR  = (60,  120, 220)
PUSH_COLOR     = (220, 140,  40)
DEPOT_COLOR    = (155,  60, 195)
TEXT_COLOR     = (210, 215, 230)
DIM_COLOR      = (100, 105, 120)
PANEL_LABEL_BG = (20,  22,  36)

GATE_NODES   = {"GATE_A1", "GATE_A2", "GATE_A3", "GATE_B1", "GATE_B2", "GATE_B3"}
RUNWAY_NODES = {"RWY_09L_ENTRY", "RWY_09R_ENTRY"}

FPS = 30   # display FPS


# ── Coordinate helper ─────────────────────────────────────────────────────────

def _panel_pos(node: str) -> tuple[int, int]:
    """Map a world node name to pixel coords within one panel surface."""
    x, y = NODE_POSITIONS.get(node, (0, 0))
    return (int(x * SCALE_X), int(y * SCALE_Y))


# ── Panel renderer ────────────────────────────────────────────────────────────

class PanelRenderer:
    """
    Draws one simulation side (FCFS or Agent) onto a pygame.Surface.
    Does NOT call pygame.init() — the main loop owns that.
    """

    def __init__(self) -> None:
        self._font_sm  = None   # initialised lazily after pygame.init()
        self._font_md  = None

    def _init_fonts(self) -> None:
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 11)
            self._font_md = pygame.font.SysFont("monospace", 13)

    def draw(
        self,
        surface:   pygame.Surface,
        graph:     object,          # nx.DiGraph
        aircraft:  list,
        vehicles:  list,
        sim_time:  float,
        label:     str,
        label_color,
    ) -> None:
        self._init_fonts()
        surface.fill(BG_COLOR)

        self._draw_taxiways(surface, graph)
        self._draw_runways(surface)
        self._draw_gates(surface)
        self._draw_depot(surface)
        self._draw_vehicles(surface, vehicles)
        self._draw_aircraft(surface, aircraft)
        self._draw_label(surface, label, label_color, sim_time)

    # ── Sub-drawers ───────────────────────────────────────────────────────────

    def _draw_taxiways(self, surf: pygame.Surface, graph) -> None:
        drawn: set = set()
        for u, v in graph.edges():
            key = tuple(sorted([u, v]))
            if key in drawn:
                continue
            drawn.add(key)
            p1 = _panel_pos(u)
            p2 = _panel_pos(v)
            occ = graph[u][v].get("occupied_by")
            color = TAXIWAY_OCC if occ else TAXIWAY_COLOR
            pygame.draw.line(surf, color, p1, p2, 2)

        for node in graph.nodes():
            if node in GATE_NODES or node in RUNWAY_NODES:
                continue
            pos = _panel_pos(node)
            pygame.draw.circle(surf, (100, 100, 115), pos, 3)

    def _draw_runways(self, surf: pygame.Surface) -> None:
        for src, dst in [("INTER_NW", "RWY_09L_ENTRY"), ("INTER_NE", "RWY_09R_ENTRY")]:
            pygame.draw.line(surf, RUNWAY_COLOR, _panel_pos(src), _panel_pos(dst), 7)
        for node in RUNWAY_NODES:
            pos = _panel_pos(node)
            pygame.draw.circle(surf, RUNWAY_COLOR, pos, 9)
            lbl = self._font_sm.render(node.replace("RWY_", ""), True, (170, 255, 170))
            surf.blit(lbl, (pos[0] + 10, pos[1] - 6))

    def _draw_gates(self, surf: pygame.Surface) -> None:
        for node in GATE_NODES:
            pos = _panel_pos(node)
            pygame.draw.circle(surf, GATE_COLOR, pos, 10, 2)
            lbl = self._font_sm.render(node.replace("GATE_", ""), True, GATE_COLOR)
            surf.blit(lbl, (pos[0] - 7, pos[1] + 12))

    def _draw_depot(self, surf: pygame.Surface) -> None:
        pos = _panel_pos("DEPOT")
        rect = pygame.Rect(pos[0] - 15, pos[1] - 10, 30, 20)
        pygame.draw.rect(surf, DEPOT_COLOR, rect, 2)
        lbl = self._font_sm.render("DEPOT", True, DEPOT_COLOR)
        surf.blit(lbl, (pos[0] - 17, pos[1] + 12))

    def _draw_aircraft(self, surf: pygame.Surface, aircraft: list) -> None:
        import math
        for ac in aircraft:
            if ac.state in (AircraftState.APPROACHING, AircraftState.DEPARTED):
                continue
            pos = NODE_POSITIONS.get(ac.position)
            if pos is None:
                continue
            px = int(pos[0] * SCALE_X)
            py = int(pos[1] * SCALE_Y)

            heading = 0.0
            if ac.path:
                nx_pos = NODE_POSITIONS.get(ac.path[0])
                if nx_pos:
                    heading = math.atan2(
                        nx_pos[1] * SCALE_Y - py,
                        nx_pos[0] * SCALE_X - px,
                    )

            color = AC_HOLD_COLOR if ac.state == AircraftState.SERVICING else AC_COLOR
            sz = 10
            tip   = (px + math.cos(heading)*sz,       py + math.sin(heading)*sz)
            left  = (px + math.cos(heading+2.4)*sz*0.6, py + math.sin(heading+2.4)*sz*0.6)
            right = (px + math.cos(heading-2.4)*sz*0.6, py + math.sin(heading-2.4)*sz*0.6)
            pygame.draw.polygon(surf, color, [tip, left, right])

            lbl = self._font_sm.render(ac.flight_id, True, color)
            surf.blit(lbl, (px + 12, py - 7))
            st_lbl = self._font_sm.render(ac.state.value[:3].upper(), True, DIM_COLOR)
            surf.blit(st_lbl, (px + 12, py + 3))

    def _draw_vehicles(self, surf: pygame.Surface, vehicles: list) -> None:
        for v in vehicles:
            pos = NODE_POSITIONS.get(v.position)
            if pos is None:
                continue
            px = int(pos[0] * SCALE_X)
            py = int(pos[1] * SCALE_Y)

            if v.vehicle_type == "fuel_truck":
                color = FUEL_COLOR
            elif v.vehicle_type == "baggage_tug":
                color = BAGGAGE_COLOR
            else:
                color = PUSH_COLOR

            sz = 6
            rect = pygame.Rect(px - sz, py - sz, sz * 2, sz * 2)
            if v.state == VehicleState.SERVICING:
                pygame.draw.rect(surf, color, rect)
            else:
                pygame.draw.rect(surf, color, rect, 2)

            lbl = self._font_sm.render(v.vehicle_id, True, color)
            surf.blit(lbl, (px + 8, py - 6))

    def _draw_label(
        self,
        surf: pygame.Surface,
        label: str,
        color,
        sim_time: float,
    ) -> None:
        """Floating label bar at the top of the panel."""
        bar_h = 28
        pygame.draw.rect(surf, PANEL_LABEL_BG, pygame.Rect(0, 0, PANEL_W, bar_h))
        pygame.draw.line(surf, color, (0, bar_h), (PANEL_W, bar_h), 1)
        lbl = self._font_md.render(f"  {label}", True, color)
        surf.blit(lbl, (4, 6))


# ── Environment subclass: reset without auto-advancing ───────────────────────

class _DemoAirportEnv(AirportEnv):
    """
    AirportEnv that skips the auto-advance-to-first-decision-point in reset().
    We advance manually so both sides start at identical t=0.
    """

    def reset(self, *, seed=None, options=None):
        # Swap out _advance_to_decision with a no-op, call super, restore.
        _orig = self._advance_to_decision
        self._advance_to_decision = lambda: 0.0
        obs, info = super().reset(seed=seed, options=options)
        self._advance_to_decision = _orig
        return obs, info


# ── FCFS runner ───────────────────────────────────────────────────────────────

class FCFSRunner:
    """Wraps the FCFS Dispatcher for step-by-step advancement."""

    def __init__(self, schedule_path: str) -> None:
        self.G        = build_taxiway_graph()
        self.gates    = build_gates()
        self.runways  = build_runways()
        fleet         = _build_fleet()
        aircraft_list = load_schedule(schedule_path)

        self.dispatcher = Dispatcher(
            graph=self.G, gates=self.gates, runways=self.runways,
            aircraft=aircraft_list, vehicles=fleet,
        )
        # Pre-mark gates for departure-only aircraft
        for ac in aircraft_list:
            if ac.state == AircraftState.AT_GATE and ac.assigned_gate is not None:
                gate = self.dispatcher.gates.get(ac.assigned_gate)
                if gate is not None:
                    gate.occupied_by = ac.flight_id

        self.sim_time       = 0.0
        self._prev_conflicts = 0
        self.done           = False

    def advance_one_second(self) -> None:
        if self.done:
            return
        self.dispatcher.tick(self.sim_time, dt=1.0)
        self.sim_time += 1.0

        new_c = self.dispatcher.conflict_count - self._prev_conflicts
        if new_c > 0:
            raise RuntimeError(
                f"FATAL: CONFLICT in FCFS at t={self.sim_time:.0f}s — "
                "this is a simulation bug."
            )
        self._prev_conflicts = self.dispatcher.conflict_count

        if all(a.state == AircraftState.DEPARTED
               for a in self.dispatcher.aircraft.values()):
            self.done = True

    @property
    def aircraft(self) -> list:
        return list(self.dispatcher.aircraft.values())

    @property
    def vehicles(self) -> list:
        return list(self.dispatcher.vehicles.values())

    def metrics(self) -> dict:
        return self.dispatcher.metrics()


# ── RL runner ─────────────────────────────────────────────────────────────────

class RLRunner:
    """
    Wraps AirportEnv + MaskablePPO model for step-by-step advancement.
    Applies model actions at every decision point; checks for illegal actions
    and conflicts after each tick.
    """

    def __init__(self, schedule_path: str, checkpoint_path: str) -> None:
        try:
            from sb3_contrib import MaskablePPO
        except ImportError:
            raise ImportError(
                "sb3_contrib not installed. Run: pip install sb3-contrib"
            )

        self.env   = _DemoAirportEnv(schedule_path=schedule_path)
        self.model = MaskablePPO.load(checkpoint_path)

        obs, _ = self.env.reset()
        self._prev_conflicts = 0
        self.done = False

    def advance_one_second(self) -> None:
        if self.done:
            return

        env = self.env

        # Apply model action if at a decision point (BEFORE ticking)
        if env._has_decision_point():
            obs   = env._build_obs()
            masks = env.action_masks()
            action, _ = self.model.predict(obs, action_masks=masks, deterministic=True)
            action = int(action)

            # Strict legality check — MaskablePPO should never violate this
            if action != ACTION_HOLD and not env._is_valid_assignment(action):
                raise RuntimeError(
                    f"FATAL: Trained policy produced ILLEGAL action {action} "
                    f"at t={env._sim_time:.0f}s.\n"
                    f"  pending_tasks  : {len(env.dispatcher.pending_tasks)}\n"
                    f"  action_masks   : {masks}\n"
                    "This is a training or environment bug — halting."
                )

            if action != ACTION_HOLD:
                env._assign_one_task(action)

        # Tick one second
        env.dispatcher.tick(env._sim_time, dt=1.0)
        env._sim_time += 1.0

        # Conflict check
        new_c = env.dispatcher.conflict_count - self._prev_conflicts
        if new_c > 0:
            raise RuntimeError(
                f"FATAL: CONFLICT detected in Trained Agent at t={env._sim_time:.0f}s.\n"
                f"  conflict_count: {env.dispatcher.conflict_count}\n"
                "This is a simulation bug — halting."
            )
        self._prev_conflicts = env.dispatcher.conflict_count

        if all(a.state == AircraftState.DEPARTED
               for a in env.dispatcher.aircraft.values()):
            self.done = True

    @property
    def sim_time(self) -> float:
        return self.env._sim_time

    @property
    def dispatcher(self):
        return self.env.dispatcher

    @property
    def aircraft(self) -> list:
        return list(self.env.dispatcher.aircraft.values())

    @property
    def vehicles(self) -> list:
        return list(self.env.dispatcher.vehicles.values())

    def metrics(self) -> dict:
        return self.env.dispatcher.metrics()


# ── Replay rendering ──────────────────────────────────────────────────────────

def _render_replay_frame(
    screen:       pygame.Surface,
    score_surf:   pygame.Surface,
    left_surf:    pygame.Surface,
    right_surf:   pygame.Surface,
    panel_renderer: PanelRenderer,
    graph,
    ctrl:         ReplayController,
) -> None:
    frame = ctrl.current_frame

    fcfs_aircraft, fcfs_vehicles = proxies_from_snapshot(frame.fcfs)
    ag_aircraft,   ag_vehicles   = proxies_from_snapshot(frame.agent)

    panel_renderer.draw(
        left_surf, graph, fcfs_aircraft, fcfs_vehicles,
        frame.sim_time, "FCFS  Baseline", (200, 130, 60),
    )
    panel_renderer.draw(
        right_surf, graph, ag_aircraft, ag_vehicles,
        frame.sim_time, "Trained  Agent", (60, 200, 130),
    )

    draw_scoreboard(
        score_surf,
        frame.fcfs["metrics"],
        frame.agent["metrics"],
        frame.sim_time,
        paused=True,
        replay_mode=True,
        replay_index=ctrl.index,
        replay_total=ctrl.total,
    )

    screen.blit(score_surf, (0, 0))
    screen.blit(left_surf,  (0,       SCORE_H))
    screen.blit(right_surf, (PANEL_W, SCORE_H))

    # Centre divider
    pygame.draw.line(screen, (40, 45, 65),
                     (PANEL_W, SCORE_H), (PANEL_W, WINDOW_H), 2)
    pygame.display.flip()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="KFIC split-screen demo: FCFS vs. Trained Agent"
    )
    parser.add_argument("--checkpoint", required=True,
                        help="Path to MaskablePPO checkpoint (.zip)")
    parser.add_argument("--scenario",   required=True,
                        help="Path to scenario JSON (e.g. demo/scenarios/medium.json)")
    parser.add_argument("--speed",  type=int, default=60,
                        help="Sim-seconds per wall-second (default 60)")
    parser.add_argument("--fps",    type=int, default=FPS,
                        help="Display FPS (default 30)")
    parser.add_argument("--record", default=None,
                        help="Save window to mp4 (e.g. --record demo.mp4)")
    parser.add_argument("--seed",   type=int, default=0,
                        help="RNG seed (reserved for future stochastic elements)")
    args = parser.parse_args()

    scenario_path    = args.scenario
    checkpoint_path  = args.checkpoint
    speed            = args.speed
    display_fps      = args.fps
    record_path      = args.record

    # Validate inputs
    if not Path(scenario_path).exists():
        print(f"[error] Scenario not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)
    if not Path(checkpoint_path).exists():
        print(f"[error] Checkpoint not found: {checkpoint_path}", file=sys.stderr)
        sys.exit(1)

    # ── Build runners (identical schedule, t=0) ────────────────────────────
    print(f"[demo] Loading scenario: {scenario_path}")
    print(f"[demo] Loading checkpoint: {checkpoint_path}")
    fcfs_runner = FCFSRunner(schedule_path=scenario_path)
    rl_runner   = RLRunner(schedule_path=scenario_path, checkpoint_path=checkpoint_path)

    # Graph is shared (immutable topology; each runner has its own copy).
    # Use FCFS runner's graph for rendering (topology is identical).
    graph = fcfs_runner.G

    # ── Replay recorder ────────────────────────────────────────────────────
    recorder_obj = ReplayRecorder()

    # ── Optional video recorder ────────────────────────────────────────────
    video_recorder = None
    if record_path:
        from demo.recorder import Recorder
        video_recorder = Recorder(record_path, fps=display_fps)

    # ── Pygame init ────────────────────────────────────────────────────────
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(
        "KFIC Demo — FCFS Baseline  vs.  Trained Agent"
    )
    clock = pygame.time.Clock()

    score_surf = pygame.Surface((WINDOW_W, SCORE_H))
    left_surf  = pygame.Surface((PANEL_W,  PANEL_H))
    right_surf = pygame.Surface((PANEL_W,  PANEL_H))

    panel_renderer = PanelRenderer()

    # ── Simulation state ───────────────────────────────────────────────────
    paused       = False
    episode_done = False
    sim_seconds_per_frame = max(1, speed // display_fps)

    print(f"[demo] speed={speed}×  fps={display_fps}  "
          f"sim-sec/frame={sim_seconds_per_frame}")
    print("[demo] SPACE=pause  ←/→=step  ESC=quit")

    # ── Live loop ──────────────────────────────────────────────────────────
    while not episode_done:
        # ── Event handling ────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                if video_recorder:
                    video_recorder.close()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    if video_recorder:
                        video_recorder.close()
                    sys.exit(0)
                if event.key == pygame.K_SPACE:
                    paused = not paused

        # ── Advance sim (if not paused) ───────────────────────────────────
        if not paused:
            for _ in range(sim_seconds_per_frame):
                if fcfs_runner.done and rl_runner.done:
                    episode_done = True
                    break

                fcfs_runner.advance_one_second()
                rl_runner.advance_one_second()

                # Record snapshot every sim-second
                recorder_obj.record(
                    fcfs_runner.sim_time,
                    fcfs_runner.dispatcher,
                    rl_runner.dispatcher,
                )

            if fcfs_runner.done and rl_runner.done:
                episode_done = True

        # ── Render ────────────────────────────────────────────────────────
        panel_renderer.draw(
            left_surf, graph,
            fcfs_runner.aircraft, fcfs_runner.vehicles,
            fcfs_runner.sim_time, "FCFS  Baseline", (200, 130, 60),
        )
        panel_renderer.draw(
            right_surf, graph,
            rl_runner.aircraft, rl_runner.vehicles,
            rl_runner.sim_time, "Trained  Agent", (60, 200, 130),
        )
        draw_scoreboard(
            score_surf,
            fcfs_runner.metrics(),
            rl_runner.metrics(),
            fcfs_runner.sim_time,
            paused=paused,
        )

        screen.blit(score_surf, (0, 0))
        screen.blit(left_surf,  (0,       SCORE_H))
        screen.blit(right_surf, (PANEL_W, SCORE_H))
        pygame.draw.line(screen, (40, 45, 65),
                         (PANEL_W, SCORE_H), (PANEL_W, WINDOW_H), 2)
        pygame.display.flip()

        if video_recorder:
            video_recorder.capture(screen)

        clock.tick(display_fps)

    # ── Episode finished ───────────────────────────────────────────────────
    print("[demo] Episode complete.")
    _print_final_comparison(fcfs_runner.metrics(), rl_runner.metrics())

    if video_recorder:
        video_recorder.close()
        video_recorder = None

    # ── Replay mode ────────────────────────────────────────────────────────
    if not recorder_obj.frames:
        print("[demo] No frames recorded — exiting.")
        pygame.quit()
        return

    ctrl = ReplayController(recorder_obj.frames)
    print(f"[demo] Replay mode: {ctrl.total} frames  ← → step  ESC quit")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    ctrl.step_forward(sim_seconds_per_frame)
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    ctrl.step_backward(sim_seconds_per_frame)

        _render_replay_frame(
            screen, score_surf, left_surf, right_surf,
            panel_renderer, graph, ctrl,
        )
        clock.tick(display_fps)


# ── Utility ───────────────────────────────────────────────────────────────────

def _print_final_comparison(fcfs: dict, agent: dict) -> None:
    print()
    print("=" * 52)
    print("  FINAL COMPARISON — FCFS vs. Trained Agent")
    print("=" * 52)
    print(f"  {'Metric':<28} {'FCFS':>8}  {'Agent':>8}")
    print(f"  {'-'*28} {'--------':>8}  {'--------':>8}")

    rows = [
        ("Flights departed",   "flights_departed",    "%d",   "%d"),
        ("Flights pending",    "flights_pending",     "%d",   "%d"),
        ("Total delay (min)",  "total_delay_minutes", "%.1f", "%.1f"),
        ("Avg delay (min)",    "avg_delay_minutes",   "%.1f", "%.1f"),
        ("Max delay (min)",    "max_delay_minutes",   "%.1f", "%.1f"),
        ("Conflicts",          "conflict_count",      "%d",   "%d"),
    ]
    for label, key, fmt_f, fmt_a in rows:
        fv = fcfs.get(key, 0)
        av = agent.get(key, 0)
        print(f"  {label:<28} {fmt_f % fv:>8}  {fmt_a % av:>8}")

    delta = fcfs.get("total_delay_minutes", 0.0) - agent.get("total_delay_minutes", 0.0)
    sign  = "+" if delta >= 0 else ""
    print(f"  {'Delay improvement':<28} {sign}{delta:.1f} min (agent vs FCFS)")
    print("=" * 52)
    print()


if __name__ == "__main__":
    main()
