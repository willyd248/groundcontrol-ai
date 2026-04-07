"""
scoreboard.py — Live scoreboard rendered at the top of the demo window.

draw_scoreboard(surface, fcfs_metrics, agent_metrics, sim_time, paused, replay_mode)

Layout (full-width banner):

  ┌─ FCFS Baseline ──────────────────┬── [SIM TIME 00:00:00] ──┬─ Trained Agent ──────────────────┐
  │ Time:      00:04:10              │  [PAUSED] / [LIVE]      │ Time:      00:04:10              │
  │ Departed:  4  Pending: 2         │                         │ Departed:  5  Pending: 1         │
  │ Delay:     8.3 min               │  Agent is 3.1 min ahead │ Delay:     5.2 min               │
  │ Conflicts: 0                     │                         │ Conflicts: 0                     │
  └──────────────────────────────────┴─────────────────────────┴──────────────────────────────────┘
"""

from __future__ import annotations
import pygame

# ── Colours ──────────────────────────────────────────────────────────────────

BG           = (10,  12,  22)
BORDER       = (50,  55,  75)
TEXT         = (210, 215, 230)
DIM          = (110, 115, 130)
GREEN        = (60,  200,  90)
RED          = (230,  70,  60)
YELLOW       = (240, 200,  50)
CYAN         = (60,  210, 220)
WHITE        = (240, 240, 250)
DIVIDER      = (40,  45,  65)

FCFS_LABEL_COLOR  = (180, 130,  60)   # amber for FCFS
AGENT_LABEL_COLOR = (60,  180, 130)   # teal for Agent

# ── Font cache (initialised on first call after pygame.init()) ────────────────

_fonts: dict[int, pygame.font.Font] = {}


def _font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("monospace", size)
    return _fonts[size]


# ── Helper ───────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _blit_center(surf: pygame.Surface, text_surf: pygame.Surface, cx: int, y: int) -> None:
    surf.blit(text_surf, (cx - text_surf.get_width() // 2, y))


def _blit_right(surf: pygame.Surface, text_surf: pygame.Surface, rx: int, y: int) -> None:
    surf.blit(text_surf, (rx - text_surf.get_width(), y))


# ── Main draw function ───────────────────────────────────────────────────────

def draw_scoreboard(
    surface: pygame.Surface,
    fcfs_metrics: dict,
    agent_metrics: dict,
    sim_time: float,
    *,
    paused: bool = False,
    replay_mode: bool = False,
    replay_index: int = 0,
    replay_total: int = 0,
) -> None:
    """
    Draw the scoreboard onto `surface` (fills the entire surface).

    Parameters
    ----------
    surface       : pygame.Surface — the scoreboard region to draw into
    fcfs_metrics  : dict from dispatcher.metrics()
    agent_metrics : dict from dispatcher.metrics()
    sim_time      : current simulation time in seconds
    paused        : show PAUSED badge if True
    replay_mode   : if True, show replay controls instead of LIVE
    replay_index  : current frame index (replay mode only)
    replay_total  : total frames recorded (replay mode only)
    """
    W = surface.get_width()
    H = surface.get_height()
    surface.fill(BG)

    # Outer border
    pygame.draw.rect(surface, BORDER, pygame.Rect(0, 0, W, H), 1)

    # ── Layout columns ────────────────────────────────────────────────────────
    SIDE_W  = W // 3          # each side panel ~1/3 width
    MID_X   = W // 2          # centre of middle column
    L_CX    = SIDE_W // 2     # centre of left column
    R_CX    = W - SIDE_W // 2 # centre of right column

    # ── Row positions ─────────────────────────────────────────────────────────
    PAD   = 10
    ROW0  = PAD          # labels
    ROW1  = ROW0 + 30    # sim time / delta
    ROW2  = ROW1 + 26
    ROW3  = ROW2 + 26
    ROW4  = ROW3 + 26
    ROW5  = ROW4 + 26    # conflicts / status

    # ── Column dividers ───────────────────────────────────────────────────────
    pygame.draw.line(surface, DIVIDER, (SIDE_W, 0), (SIDE_W, H), 1)
    pygame.draw.line(surface, DIVIDER, (W - SIDE_W, 0), (W - SIDE_W, H), 1)

    F16 = _font(16)
    F14 = _font(14)
    F13 = _font(13)
    F12 = _font(12)

    # ── Left column — FCFS ───────────────────────────────────────────────────
    _blit_center(surface, F16.render("FCFS  BASELINE", True, FCFS_LABEL_COLOR), L_CX, ROW0)

    fcfs_dep     = fcfs_metrics.get("flights_departed", 0)
    fcfs_pend    = fcfs_metrics.get("flights_pending",  0)
    fcfs_delay   = fcfs_metrics.get("total_delay_minutes", 0.0)
    fcfs_conf    = fcfs_metrics.get("conflict_count", 0)

    _blit_center(surface, F13.render(
        f"Departed: {fcfs_dep:2d}   Pending: {fcfs_pend:2d}", True, TEXT), L_CX, ROW1)
    delay_color = RED if fcfs_delay > 0 else GREEN
    _blit_center(surface, F14.render(
        f"Delay:  {fcfs_delay:6.1f} min", True, delay_color), L_CX, ROW2)
    _blit_center(surface, F13.render(
        f"Avg:    {fcfs_metrics.get('avg_delay_minutes',0.0):6.1f} min", True, DIM), L_CX, ROW3)
    _blit_center(surface, F13.render(
        f"Max:    {fcfs_metrics.get('max_delay_minutes',0.0):6.1f} min", True, DIM), L_CX, ROW4)
    conf_color = RED if fcfs_conf > 0 else DIM
    _blit_center(surface, F12.render(
        f"Conflicts: {fcfs_conf}", True, conf_color), L_CX, ROW5)

    # ── Right column — Trained Agent ─────────────────────────────────────────
    _blit_center(surface, F16.render("TRAINED  AGENT", True, AGENT_LABEL_COLOR), R_CX, ROW0)

    ag_dep   = agent_metrics.get("flights_departed", 0)
    ag_pend  = agent_metrics.get("flights_pending",  0)
    ag_delay = agent_metrics.get("total_delay_minutes", 0.0)
    ag_conf  = agent_metrics.get("conflict_count", 0)

    _blit_center(surface, F13.render(
        f"Departed: {ag_dep:2d}   Pending: {ag_pend:2d}", True, TEXT), R_CX, ROW1)
    delay_color = RED if ag_delay > 0 else GREEN
    _blit_center(surface, F14.render(
        f"Delay:  {ag_delay:6.1f} min", True, delay_color), R_CX, ROW2)
    _blit_center(surface, F13.render(
        f"Avg:    {agent_metrics.get('avg_delay_minutes',0.0):6.1f} min", True, DIM), R_CX, ROW3)
    _blit_center(surface, F13.render(
        f"Max:    {agent_metrics.get('max_delay_minutes',0.0):6.1f} min", True, DIM), R_CX, ROW4)
    conf_color = RED if ag_conf > 0 else DIM
    _blit_center(surface, F12.render(
        f"Conflicts: {ag_conf}", True, conf_color), R_CX, ROW5)

    # ── Centre column — clock + delta ─────────────────────────────────────────
    _blit_center(surface, F16.render(_fmt_time(sim_time), True, CYAN), MID_X, ROW0)

    # Status badge
    if replay_mode:
        badge_txt  = f"REPLAY  {replay_index + 1}/{replay_total}"
        badge_col  = YELLOW
        hint_txt   = "← → step   ESC exit"
    elif paused:
        badge_txt  = "PAUSED"
        badge_col  = YELLOW
        hint_txt   = "SPACE resume   ← → step"
    else:
        badge_txt  = "● LIVE"
        badge_col  = GREEN
        hint_txt   = "SPACE pause"

    _blit_center(surface, F14.render(badge_txt, True, badge_col), MID_X, ROW1)
    _blit_center(surface, F12.render(hint_txt,  True, DIM),       MID_X, ROW2)

    # Delta line
    delta = fcfs_delay - ag_delay
    if abs(delta) < 0.05:
        delta_txt   = "Even"
        delta_color = DIM
    elif delta > 0:
        delta_txt   = f"Agent  +{delta:.1f} min ahead"
        delta_color = GREEN
    else:
        delta_txt   = f"FCFS  +{-delta:.1f} min ahead"
        delta_color = RED

    _blit_center(surface, F14.render(delta_txt, True, delta_color), MID_X, ROW3)

    # Departed delta
    dep_delta = ag_dep - fcfs_dep
    if dep_delta > 0:
        dep_txt   = f"Agent +{dep_delta} more departed"
        dep_color = GREEN
    elif dep_delta < 0:
        dep_txt   = f"FCFS +{-dep_delta} more departed"
        dep_color = RED
    else:
        dep_txt   = "Equal departures"
        dep_color = DIM
    _blit_center(surface, F12.render(dep_txt, True, dep_color), MID_X, ROW4)
