"""Source-driven tests for AICadetsWaveCadet.cl using mocked observations."""
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from cl_harness import Vector, load_controller

SOURCE = (Path(__file__).resolve().parents[1] / "addons" / "AICadetsWaveCadet.cl").read_text()


class CLList:
    def __init__(self, items=None):
        self.items = list(items or [])

    @property
    def Count(self):
        return len(self.items)

    def append(self, item):
        self.items.append(item)

    def __iter__(self):
        return iter(self.items)


class Cadet:
    def __init__(self):
        self.Position = Vector(4, 0, 0)
        self.Velocity = Vector(0, 0, 0)
        self.Forward = Vector(0, 0, 1)
        self.CurrentGas = 120.0
        self.MaxGas = 120.0
        self.AutoRefillGas = False
        self.IsAlive = self.IsMine = self.LeftHookEnabled = self.LeftHookReady = True
        self.IsHookedLeft = False
        self.Grounded = True
        self.ViewID = 777
        self.Name = "Levi"
        self.ai_state = "Idle"
        self.attacking = False
        self.calls = []

    def SetDisplayName(self, name, tag):
        self.calls.append(("name", name, tag))

    def Idle(self):
        self.ai_state = "Idle"
        self.calls.append(("idle",))

    def GetAIState(self):
        return self.ai_state

    def AimAt(self, position):
        self.calls.append(("aim", position))

    def Move(self, direction):
        self.calls.append(("move", direction))

    def MoveTo(self, position, range):
        self.ai_state = "MoveTo"
        self.calls.append(("move_to", position, range))

    def MoveToTarget(self, target, range):
        self.ai_state = "MoveTo"
        self.calls.append(("move_to_target", target, range))

    def Jump(self):
        self.calls.append(("jump",))

    def LaunchHookLeft(self, position):
        self.LeftHookReady = False
        self.calls.append(("launch", position))

    def UseGas(self, enabled):
        self.calls.append(("gas", enabled))

    def Attack(self, enabled):
        self.attacking = enabled
        self.calls.append(("attack", enabled))

    def ReleaseHookLeft(self):
        self.IsHookedLeft = False
        self.calls.append(("release_left",))

    def ReleaseHookRight(self):
        self.calls.append(("release_right",))


class Titan:
    def __init__(self, view_id=101):
        self.Type = "Titan"
        self.ViewID = view_id
        self.IsAlive = True
        self.IsCrawler = False
        self.Position = Vector(0, 0, 40)
        self.NapePosition = Vector(0, 8, 42)
        self.Forward = Vector(0, 0, -1)


class World:
    def __init__(self):
        self.cadet = Cadet()
        self.titan = Titan()
        self.time = NS(GameTime=0.0)
        self.host = NS(Character=NS(Type="Human", IsAlive=True, Position=Vector(0, 0, 0), Forward=Vector(0, 0, 1), Right=Vector(1, 0, 0)))
        self.network = NS(IsMasterClient=True, MyPlayer=self.host)
        self.messages = []
        self.persistent = {}
        self.supply_stations = CLList()
        self.spawns = 0
        self.ai_humans = CLList()
        self.titans = CLList([self.titan])
        self.humans = CLList([self.cadet])
        self.player_humans = CLList([self.host.Character])
        self.hit = None
        self.controller = load_controller(
            {
                "Vector3": Vector,
                "Time": self.time,
                "Network": self.network,
                "PersistentData": NS(
                    SetProperty=lambda k, v: self.persistent.__setitem__(k, v),
                    GetProperty=lambda k, default: self.persistent.get(k, default),
                    SaveToFile=lambda f, e: True,
                ),
                "Game": NS(
                    SpawnHumanAt=self.spawn,
                    AIHumans=self.ai_humans,
                    Titans=self.titans,
                    Humans=self.humans,
                    PlayerHumans=self.player_humans,
                    IsEnding=False,
                    Print=self.messages.append,
                ),
                "Physics": NS(LineCast=self.cast),
                "Map": NS(FindMapObjectsByComponent=lambda name: self.supply_stations if name == "SupplyStation" else CLList()),
                "Convert": NS(ToString=str),
                "Range": lambda a, b, c: range(a, b, c),
                "LoadoutEnum": NS(HumanBlades="Blades"),
                "CollideWithEnum": NS(MapObjects="map", MapEditor="editor"),
            },
            SOURCE,
            class_name="AICadetsWaveCadet",
        )
        self.controller.OnGameStart()

    def spawn(self, costume, name, loadout, position, rotation):
        self.spawns += 1
        self.cadet.Position = position
        self.ai_humans.append(self.cadet)
        self.humans.append(self.cadet)
        return self.cadet

    def cast(self, start, end, layer):
        if callable(self.hit):
            return self.hit(start, end, layer)
        return self.hit

    def tick(self, dt=0.02):
        self.time.GameTime += dt
        self.controller.OnTick()


class WaveM2Tests(unittest.TestCase):
    def test_spawns_and_enters_targeting(self):
        w = World()
        w.tick()
        self.assertEqual(w.spawns, 1)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_second_game_start_does_not_terminate_live_controller(self):
        w = World()
        w.tick()
        self.assertEqual(w.spawns, 1)
        self.assertNotEqual(w.controller._state, "Done")
        w.controller.OnGameStart()
        self.assertNotEqual(w.controller._state, "Done")
        w.tick(0.4)
        self.assertNotEqual(w.controller._state, "Done")
        self.assertEqual(w.spawns, 1)
        self.assertTrue(any("duplicate_start_ignored" in m for m in w.messages))

    def test_spawn_latch_is_independent_of_terminal_state(self):
        w = World()
        w.tick()
        self.assertEqual(w.spawns, 1)
        self.assertTrue(w.controller._spawnLatched)
        self.assertNotEqual(w.controller._state, "Done")
        self.assertIn("AICadetsM2RunId-AICadetsM2-1", w.persistent)
        self.assertEqual(w.persistent["AICadetsM2TerminalReason-AICadetsM2-1"], "none")

    def test_termination_exposes_reason_and_timestamp(self):
        w = World()
        w.tick()
        w.controller.Terminate("failure", "unit_test_shutdown")
        self.assertEqual(w.controller._state, "Done")
        self.assertEqual(w.persistent["AICadetsM2State-AICadetsM2-1"], "Done")
        self.assertEqual(w.persistent["AICadetsM2TerminalReason-AICadetsM2-1"], "unit_test_shutdown")
        self.assertEqual(w.persistent["AICadetsM2TerminalTime-AICadetsM2-1"], w.time.GameTime)
        w.persistent.update({"AICadetsCmdSequence": 3, "AICadetsCmdScope": "all", "AICadetsCmdMode": "Explore"})
        w.tick()
        self.assertNotIn("AICadetsM2AckSeq-AICadetsM2-1", w.persistent)

    def test_critical_gas_switches_to_supply_search_without_refill_cheating(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 2.0
        w.tick()
        self.assertEqual(w.controller._state, "SeekSupply")
        self.assertEqual(w.cadet.CurrentGas, 2.0)
        w.tick()
        self.assertEqual(w.controller._state, "ExploreSupply")
        self.assertTrue(any("supply_not_visible" in m for m in w.messages))

    def test_confirmed_kill_flow(self):
        w = World()
        w.tick()
        w.tick(0.4)
        # Force attack window.
        w.cadet.Position = Vector(0, 8, 42)
        w.controller._target = w.titan
        w.controller._targetViewId = w.titan.ViewID
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        self.assertEqual(w.controller._state, "Strike")
        w.controller.OnCharacterDie(w.titan, w.cadet, "AICadetsM2-1")
        w.titan.IsAlive = False
        w.tick(0.35)
        w.tick()
        self.assertIn(w.controller._state, ("AcquireTarget", "Regroup"))
        self.assertTrue(any("confirmed_kill=true" in m for m in w.messages))

    def test_distant_titan_is_targeted_instead_of_discarded(self):
        # Regression: City Wave spawns can place Titans well outside 220 units.
        w = World()
        w.tick()
        w.titan.Position = Vector(0, 0, 600)
        w.titan.NapePosition = Vector(0, 8, 602)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertTrue(any("target_selected" in m and "distance=" in m for m in w.messages))

    def test_distant_target_first_walks_then_dispatches_hook_near_titan(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(0, 0, 600)
        w.titan.NapePosition = Vector(0, 8, 602)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertTrue(any(action[0] == "move_to_target" for action in w.cadet.calls))
        # Mock physical progress from the engine's continuing MoveToTarget state.
        w.cadet.Position = Vector(0, 0, 570)
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        w.hit = NS(Point=Vector(0, 20, 610), Distance=44.0)
        w.tick()
        self.assertEqual(w.controller._state, "TraverseAttach")
        self.assertTrue(any(action[0] == "launch" for action in w.cadet.calls))

    def test_empty_roster_is_reported_and_throttled(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        self.assertEqual(w.controller._state, "Explore")
        self.assertTrue(any("reason=no_alive_titans listed=0 alive=0" in m for m in w.messages))
        w.controller._exploreNextAction = 100.0
        w.tick(0.4)
        self.assertEqual(w.controller._state, "Explore")
        self.assertTrue(w.controller._exploreNextScan > w.time.GameTime)
        w.tick(2.2)
        self.assertEqual(w.controller._state, "Explore")

    def test_wide_traversal_budget_remains_bounded(self):
        w = World()
        self.assertGreaterEqual(w.controller.MaxTraversePerTarget, 20)
        self.assertLessEqual(w.controller.MaxTraversePerTarget, 40)

    def test_empty_roster_starts_exploration_not_idle_regroup(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        self.assertEqual(w.controller._state, "Explore")
        self.assertTrue(any("no_target_start_patrol" in m for m in w.messages))

    def test_exploration_uses_physical_hook_maneuver_with_surface(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.hit = NS(Point=Vector(4, 20, 48), Distance=46.0)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "TraverseAttach")
        self.assertTrue(any(a[0] == "launch" for a in w.cadet.calls))

    def test_exploration_ground_fallback_without_hookable_surface(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.controller.Enter("Explore", "test")
        w.controller._exploreFailures = 3
        w.tick()
        self.assertEqual(w.controller._state, "ExploreGround")
        self.assertTrue(any(a[0] == "move_to" for a in w.cadet.calls))
        self.assertEqual(w.cadet.ai_state, "MoveTo")

    def test_persistent_patrol_not_interrupted_by_repeated_anchor_search(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.controller.Enter("Explore", "test")
        w.controller._exploreFailures = 3
        w.tick()
        self.assertEqual(w.controller._state, "ExploreGround")
        calls_before = list(w.cadet.calls)
        w.tick(3.0)
        self.assertEqual(w.controller._state, "ExploreGround")
        self.assertEqual(w.cadet.ai_state, "MoveTo")
        self.assertEqual(w.cadet.calls, calls_before)
        w.tick(2.1)
        self.assertTrue(any("motion_observed" in m and "kind=ground_explore" in m for m in w.messages))
        self.assertEqual(w.controller._state, "ExploreGround")

    def test_distant_titan_dispatches_persistent_ground_chase(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(0, 0, 600)
        w.titan.NapePosition = Vector(0, 8, 602)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertEqual(w.cadet.ai_state, "MoveTo")
        self.assertTrue(any(call[0] == "move_to_target" for call in w.cadet.calls))
        self.assertTrue(any("motion_command" in m and "kind=ground_target" in m for m in w.messages))
        w.tick(5.1)
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertTrue(any("motion_observed" in m for m in w.messages))

    def test_ground_chase_reaches_hook_distance_without_fake_motion(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(0, 0, 600)
        w.titan.NapePosition = Vector(0, 8, 602)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "ApproachGround")
        w.cadet.Position = Vector(0, 0, 560)
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertTrue(any("motion_destination_near" in m for m in w.messages))

    def test_specific_order_does_not_control_unselected_cadet(self):
        w = World()
        w.tick()
        w.persistent.update({
            "AICadetsCmdSequence": 1,
            "AICadetsCmdMode": "Hold",
            "AICadetsCmdScope": "AICadetsM2-2",
        })
        w.tick()
        self.assertNotEqual(w.controller._state, "Hold")

    def test_order_ack_is_written_only_by_live_m2_controller(self):
        w = World()
        w.tick()
        self.assertIn("AICadetsM2Heartbeat-AICadetsM2-1", w.persistent)
        w.persistent.update({
            "AICadetsCmdSequence": 9,
            "AICadetsCmdMode": "Hold",
            "AICadetsCmdScope": "all",
        })
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertEqual(w.persistent["AICadetsM2AckSeq-AICadetsM2-1"], 9)
        self.assertEqual(w.persistent["AICadetsM2AckMode-AICadetsM2-1"], "Hold")
        self.assertEqual(w.persistent["AICadetsM2AckState-AICadetsM2-1"], "Hold")
        self.assertEqual(w.persistent["AICadetsM2State-AICadetsM2-1"], "Hold")
        self.assertTrue(any("order_applied" in x and "seq=9" in x for x in w.messages))

    def test_scope_mismatch_does_not_emit_false_ack(self):
        w = World()
        w.tick()
        w.persistent.update({
            "AICadetsCmdSequence": 6,
            "AICadetsCmdMode": "Explore",
            "AICadetsCmdScope": "AICadetsM2-2",
        })
        w.tick()
        self.assertNotIn("AICadetsM2AckSeq-AICadetsM2-1", w.persistent)
        self.assertTrue(any("order_ignored" in x for x in w.messages))

    def test_hold_release_restores_explore_and_ack_without_new_cadet(self):
        w = World()
        w.tick()
        w.persistent.update({
            "AICadetsCmdSequence": 1,
            "AICadetsCmdMode": "Hold",
            "AICadetsCmdScope": "AICadetsM2-1",
        })
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        w.persistent.update({
            "AICadetsCmdSequence": 2,
            "AICadetsCmdMode": "Explore",
            "AICadetsCmdScope": "all",
        })
        w.tick()
        self.assertEqual(w.controller._state, "Explore")
        self.assertEqual(w.persistent["AICadetsM2AckSeq-AICadetsM2-1"], 2)
        self.assertEqual(w.persistent["AICadetsM2AckState-AICadetsM2-1"], "Explore")
        self.assertEqual(w.spawns, 1)

    def test_hold_explore_engage_orders_switch_states(self):
        w = World()
        w.tick()
        w.persistent.update({
            "AICadetsCmdSequence": 1,
            "AICadetsCmdMode": "Hold",
            "AICadetsCmdScope": "all",
        })
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        w.persistent["AICadetsCmdSequence"] = 2
        w.persistent["AICadetsCmdMode"] = "Explore"
        w.tick()
        self.assertEqual(w.controller._state, "Explore")
        w.persistent["AICadetsCmdSequence"] = 3
        w.persistent["AICadetsCmdMode"] = "Engage"
        w.tick()
        self.assertEqual(w.controller._orderMode, "Engage")
        self.assertEqual(w.controller._state, "PlanApproach")

    def test_low_gas_enters_resupply_instead_of_terminating(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 31.0
        w.tick()
        self.assertEqual(w.controller._state, "SeekSupply")
        self.assertTrue(w.cadet.AutoRefillGas)
        self.assertTrue(any("resupply_requested" in m for m in w.messages))

    def test_supply_station_is_selected_and_ground_routed(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 32.0
        w.supply_stations.append(NS(Position=Vector(4, 0, 60)))
        w.tick()
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "SeekSupply")
        self.assertEqual(w.controller._supplySource, "map_component")
        self.assertTrue(any(x[0] == "move_to" for x in w.cadet.calls))

    def test_host_marker_routes_when_station_not_exposed(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 28.0
        w.persistent.update({
            "AICadetsSupplyRevision": 1,
            "AICadetsSupplyX": 4.0,
            "AICadetsSupplyY": 0.0,
            "AICadetsSupplyZ": 30.0,
        })
        w.tick()
        w.tick()
        self.assertEqual(w.controller._supplySource, "host_marked_unverified")
        self.assertTrue(any(x[0] == "move_to" for x in w.cadet.calls))

    def test_arrival_alone_does_not_refill(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 25.0
        w.supply_stations.append(NS(Position=Vector(4, 0, 1)))
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "AtSupply")
        w.tick(1)
        self.assertEqual(w.controller._state, "AtSupply")
        self.assertFalse(any("resupply_verified" in x for x in w.messages))

    def test_actual_gas_increase_resumes_engage(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 20.0
        w.supply_stations.append(NS(Position=Vector(4, 0, 1)))
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "AtSupply")
        w.cadet.CurrentGas = 111.0
        w.tick()
        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertFalse(w.cadet.AutoRefillGas)
        self.assertTrue(any("resupply_verified" in x for x in w.messages))

    def test_unmapped_supply_search_patrol_can_detect_natural_refill(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 9.0
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "ExploreSupply")
        w.tick()
        self.assertTrue(any(a[0] == "move_to" for a in w.cadet.calls))
        self.assertTrue(w.cadet.AutoRefillGas)
        # Simulate a real in-game station's own refill, not a controller write.
        w.cadet.CurrentGas = 99.0
        w.tick()
        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertFalse(w.cadet.AutoRefillGas)
        self.assertTrue(any("resupply_verified" in x for x in w.messages))

    def test_resupply_order_is_scoped_and_uses_ground_navigation(self):
        w = World()
        w.tick()
        w.persistent.update({
            "AICadetsCmdSequence": 1,
            "AICadetsCmdMode": "Resupply",
            "AICadetsCmdScope": "AICadetsM2-1",
            "AICadetsSupplyRevision": 1,
            "AICadetsSupplyX": 4.0,
            "AICadetsSupplyY": 0.0,
            "AICadetsSupplyZ": 50.0,
        })
        w.tick()
        self.assertEqual(w.controller._state, "SeekSupply")
        w.tick()
        self.assertEqual(w.controller._supplySource, "host_marked_unverified")

    def test_retry_bans_target(self):
        w = World()
        w.tick()
        w.tick(0.4)
        w.controller._target = w.titan
        w.controller._targetViewId = w.titan.ViewID
        w.controller._traverseMode = "approach"
        w.controller._trStartDistance = Vector.Distance(w.cadet.Position, w.titan.NapePosition)
        w.controller._targetRetryCount = w.controller.MaxTargetRetries
        w.controller._trOutcome = "collision_risk"
        w.controller.FinishTraverse()
        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)


if __name__ == "__main__":
    unittest.main()
