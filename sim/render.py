"""
render.py — Pygame top-down renderer for KFIC airport simulation.

Canvas: 1200×700 px
- Taxiways: grey lines
- Gates: labelled cyan circles
- Runways: green rectangles
- Aircraft: yellow triangles (pointing in direction of travel)
- Vehicles:
    FuelTruck      → red square
    BaggageTug     → blue square
    PushbackTractor → orange square
- HUD: top-right panel with clock, metrics, and entity counts
"""

from __future__ import annotations
import math
import pygame
from sim.world import NODE_POSITIONS
from sim.entities import (
    Aircraft, AircraftState, FuelTruck, BaggageTug, PushbackTractor,
    VehicleState,
)

# ---- Color palette ----
BG_COLOR       = (18,  20,  30)
TAXIWAY_COLOR  = (80,  80,  90)
GATE_COLOR     = (50, 200, 200)
RUNWAY_COLOR   = (50, 160,  50)
AC_COLOR       = (255, 220,  50)
AC_HOLD_COLOR  = (255, 100,  50)
FUEL_COLOR     = (220,  60,  60)
BAGGAGE_COLOR  = (60, 120, 220)
PUSH_COLOR     = (220, 140,  40)
DEPOT_COLOR    = (160,  60, 200)
HUD_BG         = (10,  12,  20, 200)
TEXT_COLOR     = (220, 220, 220)
CONFLICT_COLOR = (255,   0,   0)

FONT_SIZE      = 14
HUD_FONT_SIZE  = 13

GATE_NODES = {
    "GATE_A1", "GATE_A2", "GATE_A3",
    "GATE_B1", "GATE_B2", "GATE_B3",
}

RUNWAY_NODES = {"RWY_09L_ENTRY", "RWY_09R_ENTRY"}


def _node_pos(node: str) -> tuple[int, int]:
    pos = NODE_POSITIONS.get(node, (0, 0))
    return (int(pos[0]), int(pos[1]))


def _heading_between(src: str, dst: str) -> float:
    sx, sy = NODE_POSITIONS.get(src, (0, 0))
    dx, dy = NODE_POSITIONS.get(dst, (0, 0))
    return math.atan2(dy - sy, dx - sx)


class Renderer:
    def __init__(self, graph, width: int = 1200, height: int = 700) -> None:
        pygame.init()
        self.width  = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("KFIC Airport — Ground Ops Simulator")
        self.clock  = pygame.time.Clock()
        self.font   = pygame.font.SysFont("monospace", FONT_SIZE)
        self.hud_font = pygame.font.SysFont("monospace", HUD_FONT_SIZE)
        self.graph  = graph

    def handle_events(self) -> bool:
        """Return False if user requests quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        return True

    def draw(
        self,
        aircraft: list[Aircraft],
        vehicles: list,
        sim_time: float,
        metrics: dict,
        speed: int = 60,
    ) -> None:
        self.screen.fill(BG_COLOR)
        self._draw_taxiways()
        self._draw_runways()
        self._draw_gates()
        self._draw_depot()
        self._draw_vehicles(vehicles)
        self._draw_aircraft(aircraft)
        self._draw_hud(sim_time, metrics, speed, aircraft, vehicles)
        pygame.display.flip()

    # -----------------------------------------------------------------------
    # Taxiways
    # -----------------------------------------------------------------------

    def _draw_taxiways(self) -> None:
        drawn = set()
        for u, v in self.graph.edges():
            edge_key = tuple(sorted([u, v]))
            if edge_key in drawn:
                continue
            drawn.add(edge_key)
            p1 = _node_pos(u)
            p2 = _node_pos(v)
            occ = self.graph[u][v].get("occupied_by")
            color = (180, 80, 80) if occ else TAXIWAY_COLOR
            pygame.draw.line(self.screen, color, p1, p2, 3)

        # Node dots
        for node in self.graph.nodes():
            if node in GATE_NODES or node in RUNWAY_NODES:
                continue
            pos = _node_pos(node)
            pygame.draw.circle(self.screen, (120, 120, 130), pos, 4)
            if node not in ("INTER_NW", "INTER_NE", "TWY_NORTH",
                            "TWY_A_ENTRY", "TWY_B_ENTRY", "TWY_SERVICE"):
                continue
            label = self.font.render(node.replace("_", " "), True, (100, 100, 110))
            self.screen.blit(label, (pos[0] + 6, pos[1] - 8))

    # -----------------------------------------------------------------------
    # Runways
    # -----------------------------------------------------------------------

    def _draw_runways(self) -> None:
        runway_segments = [
            ("INTER_NW",  "RWY_09L_ENTRY"),
            ("INTER_NE",  "RWY_09R_ENTRY"),
        ]
        for src, dst in runway_segments:
            p1 = _node_pos(src)
            p2 = _node_pos(dst)
            pygame.draw.line(self.screen, RUNWAY_COLOR, p1, p2, 8)

        for node in RUNWAY_NODES:
            pos = _node_pos(node)
            pygame.draw.circle(self.screen, RUNWAY_COLOR, pos, 10)
            label = self.font.render(node, True, (180, 255, 180))
            self.screen.blit(label, (pos[0] + 12, pos[1] - 7))

    # -----------------------------------------------------------------------
    # Gates
    # -----------------------------------------------------------------------

    def _draw_gates(self) -> None:
        for node in GATE_NODES:
            pos = _node_pos(node)
            pygame.draw.circle(self.screen, GATE_COLOR, pos, 12, 2)
            label_text = node.replace("GATE_", "")
            label = self.font.render(label_text, True, GATE_COLOR)
            self.screen.blit(label, (pos[0] - 8, pos[1] + 14))

    # -----------------------------------------------------------------------
    # Depot
    # -----------------------------------------------------------------------

    def _draw_depot(self) -> None:
        pos = _node_pos("DEPOT")
        rect = pygame.Rect(pos[0] - 18, pos[1] - 12, 36, 24)
        pygame.draw.rect(self.screen, DEPOT_COLOR, rect, 2)
        label = self.font.render("DEPOT", True, DEPOT_COLOR)
        self.screen.blit(label, (pos[0] - 20, pos[1] + 14))

    # -----------------------------------------------------------------------
    # Aircraft (triangles)
    # -----------------------------------------------------------------------

    def _draw_aircraft(self, aircraft: list[Aircraft]) -> None:
        for ac in aircraft:
            if ac.state == AircraftState.APPROACHING:
                continue
            if ac.state == AircraftState.DEPARTED:
                continue
            pos = NODE_POSITIONS.get(ac.position)
            if pos is None:
                continue

            px, py = int(pos[0]), int(pos[1])
            heading = 0.0
            if ac.path:
                heading = _heading_between(ac.position, ac.path[0])

            color = AC_HOLD_COLOR if ac.state == AircraftState.SERVICING else AC_COLOR
            self._draw_triangle(px, py, heading, 12, color)

            # Label
            label = self.hud_font.render(ac.flight_id, True, color)
            self.screen.blit(label, (px + 14, py - 8))

            # State badge
            state_label = self.hud_font.render(ac.state.value[:3].upper(), True, (160, 160, 160))
            self.screen.blit(state_label, (px + 14, py + 4))

    def _draw_triangle(self, cx: int, cy: int, heading: float, size: int, color) -> None:
        tip_x   = cx + math.cos(heading) * size
        tip_y   = cy + math.sin(heading) * size
        left_x  = cx + math.cos(heading + 2.4) * (size * 0.6)
        left_y  = cy + math.sin(heading + 2.4) * (size * 0.6)
        right_x = cx + math.cos(heading - 2.4) * (size * 0.6)
        right_y = cy + math.sin(heading - 2.4) * (size * 0.6)
        pygame.draw.polygon(
            self.screen, color,
            [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)]
        )

    # -----------------------------------------------------------------------
    # Vehicles (squares)
    # -----------------------------------------------------------------------

    def _draw_vehicles(self, vehicles: list) -> None:
        for v in vehicles:
            pos = NODE_POSITIONS.get(v.position)
            if pos is None:
                continue
            px, py = int(pos[0]), int(pos[1])

            if isinstance(v, FuelTruck):
                color = FUEL_COLOR
            elif isinstance(v, BaggageTug):
                color = BAGGAGE_COLOR
            else:
                color = PUSH_COLOR

            size = 7
            rect = pygame.Rect(px - size, py - size, size * 2, size * 2)
            if v.state == VehicleState.SERVICING:
                pygame.draw.rect(self.screen, color, rect)
            else:
                pygame.draw.rect(self.screen, color, rect, 2)

            label = self.hud_font.render(v.vehicle_id, True, color)
            self.screen.blit(label, (px + 9, py - 7))

    # -----------------------------------------------------------------------
    # HUD
    # -----------------------------------------------------------------------

    def _draw_hud(
        self,
        sim_time: float,
        metrics: dict,
        speed: int,
        aircraft: list[Aircraft],
        vehicles: list,
    ) -> None:
        hud_x, hud_y = self.width - 310, 10
        hud_w, hud_h = 295, 280

        surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
        surf.fill(HUD_BG)
        self.screen.blit(surf, (hud_x, hud_y))

        lines = [
            f"  KFIC GROUND OPS SIMULATOR",
            f"  ──────────────────────────",
            f"  SIM TIME : {_fmt_time(sim_time)}",
            f"  SPEED    : {speed}×",
            f"  ──────────────────────────",
            f"  Flights  : {metrics.get('flights_departed', 0)} departed  "
            f"{metrics.get('flights_pending', 0)} pending",
            f"  Delay    : {metrics.get('total_delay_minutes', 0.0):.1f} min total",
            f"  Avg delay: {metrics.get('avg_delay_minutes', 0.0):.1f} min",
            f"  Conflicts: {metrics.get('conflict_count', 0)}",
            f"  Veh disp : {metrics.get('vehicles_dispatched', 0)}",
            f"  ──────────────────────────",
        ]

        # Per-aircraft status
        for ac in aircraft:
            if ac.state in (AircraftState.APPROACHING, AircraftState.DEPARTED):
                continue
            lines.append(f"  {ac.flight_id:<7} {ac.state.value:<12}")

        for i, line in enumerate(lines):
            color = CONFLICT_COLOR if "Conflicts" in line and metrics.get("conflict_count", 0) > 0 \
                else TEXT_COLOR
            surf_line = self.hud_font.render(line, True, color)
            self.screen.blit(surf_line, (hud_x + 2, hud_y + 6 + i * 17))

        # Legend
        legend = [
            (AC_COLOR,     "Aircraft"),
            (FUEL_COLOR,   "Fuel truck"),
            (BAGGAGE_COLOR,"Baggage tug"),
            (PUSH_COLOR,   "Pushback"),
        ]
        lx, ly = 10, self.height - 80
        for color, text in legend:
            pygame.draw.rect(self.screen, color, pygame.Rect(lx, ly, 12, 12), 2)
            label = self.hud_font.render(text, True, TEXT_COLOR)
            self.screen.blit(label, (lx + 16, ly - 1))
            lx += 110


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
