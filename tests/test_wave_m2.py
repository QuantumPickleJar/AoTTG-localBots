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
        self.State = "Idle"
        self.CurrentAnimation = "idle"
        self.LeftHookPosition = None
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


def movement_request_count(cadet):
    return sum(1 for call in cadet.calls if call[0] in ("move", "move_to"))


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
        self.sphere_hit = None
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
                "Physics": NS(LineCast=self.cast, SphereCast=lambda start, end, radius, layer: self.sphere_hit),
                "Map": NS(FindMapObjectsByComponent=lambda name: self.supply_stations if name == "SupplyStation" else CLList()),
                "Convert": NS(ToString=str),
                "Range": lambda a, b, c: range(a, b, c),
                "LoadoutEnum": NS(HumanBlades="Blades"),
                "CollideWithEnum": NS(MapObjects="map", MapEditor="editor", Titans="titans"),
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
        self.assertTrue(any(action[0] == "move" for action in w.cadet.calls))
        self.assertFalse(any(action[0] == "move_to_target" for action in w.cadet.calls))
        # Mock physical progress from the continuing planar steering request.
        w.cadet.Position = Vector(0, 0, 570)
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        w.hit = NS(Point=Vector(0, 20, 610), Distance=44.0)
        w.tick()
        self.assertEqual(w.controller._state, "TraverseAttach")
        self.assertTrue(any(action[0] == "launch" for action in w.cadet.calls))
        self.assertTrue(any("motion_cancelled" in m and "reason=state_exit_PlanApproach" in m for m in w.messages))

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
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertTrue(any(call[0] == "move" for call in w.cadet.calls))
        self.assertFalse(any(call[0] == "move_to_target" for call in w.cadet.calls))
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
        self.assertTrue(any("motion_segment_done" in m for m in w.messages))
        self.assertTrue(any("motion_cancelled" in m and "reason=state_exit_PlanApproach" in m for m in w.messages))

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

    def test_combined_engage_presets_set_driver_and_ack_requested_mode(self):
        w = World()
        w.tick()
        for sequence, preset, driver in (
            (1, "EngageEngine", "Engine"),
            (2, "EngageDirect", "Direct"),
        ):
            w.persistent.update({
                "AICadetsCmdSequence": sequence,
                "AICadetsCmdMode": preset,
                "AICadetsCmdScope": "all",
            })
            w.tick()
            self.assertEqual(w.controller.GroundSteering, driver)
            self.assertEqual(w.controller._orderMode, "Engage")
            self.assertEqual(w.persistent["AICadetsM2AckMode-AICadetsM2-1"], preset)

    def test_manual_recovery_order_resumes_autonomous_engage(self):
        w = World()
        w.tick()
        w.controller._target = w.titan
        w.controller._targetViewId = w.titan.ViewID
        w.controller._orderMode = "Hold"
        w.controller.Enter("Hold", "test_hold")
        w.persistent.update({
            "AICadetsCmdSequence": 1,
            "AICadetsCmdMode": "Recovery",
            "AICadetsCmdScope": "all",
        })
        w.tick()
        self.assertEqual(w.controller._orderMode, "Engage")
        self.assertEqual(w.persistent["AICadetsM2AckMode-AICadetsM2-1"], "Recovery")
        self.assertTrue(any("manual_recovery_requested" in message for message in w.messages))
        self.assertNotEqual(w.controller._state, "Hold")

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

    def test_no_anchor_fallback_sustains_ground_pursuit_and_stall_patrol(self):
        w = World()
        w.tick()
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.tick()  # no map hit, ground fallback inside hook radius
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertEqual(w.cadet.calls[-1][0], "move")
        self.assertFalse(any(call[0] == "move_to_target" for call in w.cadet.calls))
        w.tick(1.0)
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertEqual(w.cadet.ai_state, "Idle")
        w.tick(4.1)
        w.tick(5.1)
        self.assertEqual(w.controller._state, "Recover")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertTrue(any(call[0] == "move" for call in w.cadet.calls))
        self.assertFalse(any(call[0] == "move_to" for call in w.cadet.calls))
        w.cadet.Position = w.controller._groundGoal
        w.tick(6.1)
        self.assertEqual(w.controller._state, "PlanApproach")
        w.controller._targetRecoveries = w.controller.RecoveryBudget()
        w.controller.Enter("Recover", "test_exhausted")
        w.tick()
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)
        w.tick()
        self.assertEqual(w.controller._state, "Observe")
        w.tick(6.1)
        self.assertIn(w.controller._state, ("AcquireTarget", "Explore"))

    def test_target_appearing_during_ground_search_interrupts_patrol(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.controller.Enter("Explore", "test")
        w.controller._exploreFailures = 3
        w.tick()
        self.assertEqual(w.controller._state, "ExploreGround")
        w.titans.append(w.titan)
        w.tick(3.0)
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_disappearance_after_strike_is_not_a_confirmed_kill(self):
        w = World()
        w.tick()
        w.controller._target = w.titan
        w.controller._targetViewId = w.titan.ViewID
        w.controller.Enter("VerifyAttack", "test")
        w.titans.items.clear()
        w.tick()
        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertTrue(any("reason=target_lost" in m for m in w.messages))
        self.assertFalse(any("confirmed_kill=true" in m for m in w.messages))

    def test_hold_stops_persistent_navigation(self):
        w = World()
        w.tick()
        w.controller.Enter("Explore", "test")
        w.controller._exploreFailures = 3
        w.tick()
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertFalse(w.cadet.attacking)

    def test_refill_resumes_explore_and_timeout_stops_navigation(self):
        w = World()
        w.tick()
        w.controller._orderMode = "Explore"
        w.cadet.CurrentGas = 20.0
        w.tick()
        w.cadet.CurrentGas = 35.0
        w.tick()
        self.assertEqual(w.controller._state, "Explore")
        self.assertEqual(w.controller._orderMode, "Explore")
        w.cadet.CurrentGas = 20.0
        w.supply_stations.append(NS(Position=Vector(4, 0, 100)))
        w.tick()
        w.tick()
        self.assertEqual(w.cadet.ai_state, "MoveTo")
        w.tick(w.controller.SupplySearchTimeout + 1)
        self.assertEqual(w.controller._state, "Hold")
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertEqual(w.cadet.CurrentGas, 20.0)

    def test_published_watcher_status_has_target_geometry_and_order(self):
        w = World()
        w.tick()
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.controller.PublishOrderStatus()
        key = "AICadetsM2-1"
        self.assertEqual(w.persistent["AICadetsM2TargetId-" + key], w.titan.ViewID)
        self.assertIn("distance=", w.persistent["AICadetsM2TargetInfo-" + key])
        self.assertIn("order_seq=", w.persistent["AICadetsM2Navigation-" + key])
        self.assertEqual(w.persistent["AICadetsM2StatusTime-" + key], w.time.GameTime)

    def test_optional_report_is_bounded_and_available_to_passive_watcher(self):
        w = World()
        w.controller.SaveRunReport = True
        w.tick()
        for i in range(3100):
            w.controller.LogEvent("sample", "n=" + str(i))
        self.assertEqual(w.controller._trace.count("\n"), 3000)
        self.assertEqual(w.persistent["AICadetsM2Report-AICadetsM2-1"], w.controller._trace)

    def test_distant_pursuit_uses_viable_odm_without_waiting_for_68_units(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(0, 0, 600)
        w.titan.NapePosition = Vector(0, 8, 602)
        w.controller.AcquireTarget()
        w.controller.PlanApproach()
        w.hit = NS(Point=Vector(4, 20, 48), Distance=46.0)
        w.tick(1.1)
        self.assertEqual(w.controller._state, "TraverseAttach")
        self.assertTrue(any(x[0] == "launch" for x in w.cadet.calls))
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_empty_travel_probe_keeps_reissuing_direct_ground_movement(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(True)
        before_moves = len([call for call in w.cadet.calls if call[0] == "move"])
        w.tick(1.1)
        after_moves = len([call for call in w.cadet.calls if call[0] == "move"])
        self.assertEqual(after_moves, before_moves + 1)
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertFalse(any(call[0] == "move_to_target" for call in w.cadet.calls))

    def test_sideways_displacement_is_not_target_progress(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(True)
        bearing = w.controller._groundBearing
        side = Vector(bearing.Z, 0, -bearing.X)
        for i in range(2):
            w.cadet.Position = w.cadet.Position + side * 5
            # Keep each window's diagnostic bearing fixed for this lateral trial.
            w.controller._groundBearing = bearing
            w.tick(5.1)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_profiles_bound_recovery_and_hold_interrupts_reposition(self):
        w = World()
        w.tick()
        w.controller.Persistence = 1
        self.assertEqual(w.controller.RecoveryBudget(), 1)
        w.controller.Persistence = 5
        self.assertEqual(w.controller.RecoveryBudget(), 3)
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertEqual(w.cadet.ai_state, "Idle")

    def test_direct_recovery_reissues_projected_move_and_hold_cancels_owned_command(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_direct_recovery_move")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertTrue(w.controller._groundRecoveryCommandActive)
        self.assertEqual(w.controller._groundRecoveryCommandDriver, "Direct")
        first_move = next(call for call in reversed(w.cadet.calls) if call[0] == "move")
        self.assertGreater(first_move[1].Magnitude, 0.9)
        self.assertFalse(any(call[0] == "move_to" for call in w.cadet.calls))
        self.assertTrue(any("kind=ground_recovery driver=Direct request=Human.Move" in line
                            for line in w.messages))

        before = movement_request_count(w.cadet)
        w.tick(0.02)
        self.assertGreater(movement_request_count(w.cadet), before)

        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        stopped_at = movement_request_count(w.cadet)
        self.assertEqual(w.controller._state, "Hold")
        self.assertFalse(w.controller._groundRecoveryCommandActive)
        self.assertEqual(w.cadet.calls[-1], ("idle",))
        w.tick(0.02)
        self.assertEqual(movement_request_count(w.cadet), stopped_at)

    def test_engine_recovery_remains_a_single_move_to_comparison(self):
        w = World()
        w.tick()
        w.controller.GroundSteering = "Engine"
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_engine_recovery_move_to")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        move_to_calls = [call for call in w.cadet.calls if call[0] == "move_to"]
        self.assertEqual(len(move_to_calls), 1)
        self.assertEqual(move_to_calls[0][1].Y, w.cadet.Position.Y)
        self.assertEqual(move_to_calls[0][2], 3.0)
        self.assertTrue(w.controller._groundRecoveryCommandActive)
        self.assertEqual(w.controller._groundRecoveryCommandDriver, "Engine")
        self.assertTrue(any("kind=ground_recovery driver=Engine request=Character.MoveTo" in line
                            for line in w.messages))
        w.tick(0.02)
        self.assertEqual(movement_request_count(w.cadet), 1)

    def test_recovery_start_and_end_keep_run_order_and_measurement_context(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_recovery_record_context")
        w.tick()
        start = next(line for line in w.messages if "event=reposition_start" in line)
        w.cadet.Position = w.controller._groundGoal
        w.tick()
        end = next(line for line in w.messages if "event=reposition_end" in line)

        required = (
            "run=m2-", "cadet=AICadetsM2-1", "order_seq=", "target_id=",
            "attempt=1", "start_pos=", "end_pos=", "moved=", "goal=",
            "target_gain=", "ai_state=", "termination_reason=",
        )
        for label, line in (("start", start), ("end", end)):
            for field in required:
                with self.subTest(event=label, field=field):
                    self.assertIn(field, line)

    def test_momentum_only_biases_new_acquisition(self):
        w = World()
        w.tick()
        behind = Titan(202)
        behind.Position = Vector(4, 0, -35)
        behind.NapePosition = Vector(4, 8, -35)
        w.titans.append(behind)
        w.cadet.Velocity = Vector(0, 0, 14)
        w.controller.AcquireTarget()
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        w.controller.StartGroundApproach(True)
        w.cadet.Velocity = Vector(0, 0, -14)
        w.tick(0.1)
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_low_gas_preempts_ground_reposition(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        w.cadet.CurrentGas = 20
        w.tick()
        self.assertEqual(w.controller._state, "SeekSupply")
        self.assertEqual(w.controller._resumeAfterSupply, "Engage")

    def test_manual_explore_remains_noncombat_with_aerial_profile(self):
        w = World()
        w.tick()
        w.controller.AerialPreference = 5
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Explore", "AICadetsCmdScope": "all"})
        for i in range(20):
            w.tick(0.5)
        self.assertEqual(w.controller._targetViewId, 0)
        self.assertFalse(any(x == ("attack", True) for x in w.cadet.calls))

    def test_direct_ground_driver_uses_move_and_stops_on_blocked_corridor(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.GroundSteering = "Direct"
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        before = len(w.cadet.calls)
        w.tick(0.1)
        self.assertEqual(w.cadet.calls[-1][0], "move")
        self.assertFalse(any(x[0] == "move_to_target" for x in w.cadet.calls[before:]))
        w.hit = NS(Point=Vector(4, 1, 3), Distance=3.0)
        w.tick(0.1)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(w.cadet.calls[-1], ("idle",))

    def test_driver_order_is_scoped_and_does_not_release_hold(self):
        w = World()
        w.tick()
        w.controller._orderMode = "Hold"
        w.controller.Enter("Hold", "test")
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "GroundDirect", "AICadetsCmdScope": "AICadetsM2-2"})
        w.tick()
        self.assertEqual(w.controller.GroundSteering, "Direct")
        w.persistent.update({"AICadetsCmdSequence": 2, "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller.GroundSteering, "Direct")
        self.assertEqual(w.controller._state, "Hold")
        self.assertEqual(w.controller._orderMode, "Hold")
        self.assertIn("ground=Direct", w.persistent["AICadetsM2Profile-AICadetsM2-1"])
        self.assertEqual(w.persistent["AICadetsM2Build-AICadetsM2-1"], "M2-locomotion-1-f8combo-7-direct-recovery")

    def test_driver_switch_restarts_only_current_pursuit(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "GroundDirect", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertEqual(w.cadet.calls[-1][0], "move")
        self.assertEqual(w.controller._orderMode, "Engage")
        w.controller.Terminate("safe_termination", "test")
        self.assertEqual(w.cadet.calls[-1], ("idle",))

    def test_hold_cancels_owned_ground_motion_on_state_exit(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertTrue(any("event=motion_cancelled" in m and "reason=order_Hold" in m and "request=Human.Idle" in m and "ai_state_after=Idle" in m for m in w.messages))

    def test_circle_path_uses_bounded_recovery_before_any_target_ban_and_hold_interrupts(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        for position in (Vector(14, 0, 0), Vector(14, 0, 10), Vector(4, 0, 10), Vector(4, 0, 0)):
            w.cadet.Position = position
            w.tick(1.0)
        w.tick(1.1)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(w.cadet.ai_state, "Idle")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertEqual(w.controller._bannedTargetViewId, 0)
        self.assertTrue(any("circling_detected" in x and "action=bounded_recovery" in x for x in w.messages))
        self.assertTrue(any("motion_cancelled" in x and "reason=state_exit_Recover" in x and "request=Human.Idle" in x for x in w.messages))
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        w.tick(7.0)
        self.assertEqual(w.controller._state, "Hold")

    def test_inefficient_path_with_forward_motion_does_not_ban_moving_target(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        for position in (Vector(14, 0, 0), Vector(14, 0, 20), Vector(4, 0, 20), Vector(4, 0, 16)):
            w.cadet.Position = position
            w.tick(1.0)
        w.titan.Position = Vector(4, 0, 616)
        w.titan.NapePosition = Vector(4, 8, 618)
        w.tick(1.1)
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertNotEqual(w.controller._bannedTargetViewId, w.titan.ViewID)
        self.assertTrue(any("target_gain=" in m for m in w.messages if "pursuit_progress" in m))
        self.assertFalse(any("circling_detected" in m for m in w.messages))

    def test_second_approach_leg_recalculates_goal_for_moving_titan(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller._traverseMode = "approach"
        w.controller._trLeg = 1
        w.controller._traverseGoal = Vector(0, 14, 59)
        w.titan.NapePosition = Vector(30, 9, 80)
        w.titan.Forward = Vector(1, 0, 0)
        w.controller.BeginTraverseLeg()
        goal = w.controller._traverseGoal
        self.assertEqual((goal.X, goal.Y, goal.Z), (13, 15, 80))
        self.assertTrue(any("approach_goal_updated" in m for m in w.messages))

    def test_closing_titan_does_not_trigger_stationary_stall(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        for z in (590, 580):
            w.titan.Position = Vector(4, 0, z)
            w.titan.NapePosition = Vector(4, 8, z + 2)
            w.tick(5.1)
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertEqual(w.controller._groundStalledChecks, 0)

    def test_lost_titan_stops_before_second_approach_hook(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller._traverseMode = "approach"
        w.controller._trLeg = 1
        w.controller._traverseGoal = Vector(0, 14, 59)
        w.titan.IsAlive = False
        w.controller.BeginTraverseLeg()
        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertFalse(any(call[0] == "launch" for call in w.cadet.calls))

    def test_observation_prevents_immediate_reacquisition_loop(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller._targetRecoveries = w.controller.RecoveryBudget()
        w.controller.Enter("Recover", "test")
        w.tick()
        calls = list(w.cadet.calls)
        for _ in range(50):
            w.tick(0.02)
        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(w.cadet.calls, calls)
        w.tick(5.1)
        self.assertEqual(w.controller._state, "AcquireTarget")

    def test_airborne_anchor_failure_waits_for_landing_without_burning_retries(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.cadet.Grounded = False
        w.controller._traverseMode = "approach"
        w.controller._trOutcome = "no_suitable_anchor"
        w.controller.FinishTraverse()
        self.assertEqual(w.controller._state, "WaitLanding")
        attempts = w.controller._targetTraverseCount
        for _ in range(50):
            w.tick(0.02)
        self.assertEqual(w.controller._targetTraverseCount, attempts)
        self.assertEqual(w.controller._state, "WaitLanding")
        w.cadet.Grounded = True
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_airborne_wait_honors_hold_and_timeout(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.cadet.Grounded = False
        w.controller._traverseMode = "recover"
        w.controller._trOutcome = "no_suitable_anchor"
        w.controller.FinishTraverse()
        w.tick(4.1)
        self.assertEqual(w.controller._state, "Observe")
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")

    def test_both_reposition_corridors_blocked_does_not_dispatch_move(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.hit = NS(Point=Vector(4, 1, 3), Distance=3.0)
        w.controller.Enter("Recover", "test")
        calls = len(w.cadet.calls)
        w.tick()
        self.assertEqual(w.controller._state, "Observe")
        self.assertFalse(any(c[0] == "move_to" for c in w.cadet.calls[calls:]))
        self.assertTrue(any("reposition_blocked" in m for m in w.messages))

    def test_tick_health_reports_game_time_and_largest_gap(self):
        w = World()
        w.tick()
        for _ in range(12):
            w.tick(1.0)
        self.assertTrue(any("event=tick_health" in m and "max_gap=" in m and "count=" in m for m in w.messages))

    def setup_close_orbit(self, style="Alternate"):
        w = World()
        w.tick()
        w.cadet.Position = Vector(0, 8, 17)
        w.cadet.Grounded = False
        w.controller.CombatArcStyle = style
        w.sphere_hit = w.titan
        w.controller.AcquireTarget()
        return w

    def test_titan_arc_requires_exact_visible_target_and_hook_readiness(self):
        w = self.setup_close_orbit()
        w.sphere_hit = Titan(202)
        self.assertFalse(w.controller.TryStartTitanOrbit())
        self.assertFalse(any(x[0] == "launch" for x in w.cadet.calls))
        w.sphere_hit = w.titan
        w.hit = NS(Point=Vector(0, 8, 25), Distance=8.0)
        self.assertFalse(w.controller.TryStartTitanOrbit())
        w.hit = None
        w.cadet.LeftHookReady = False
        self.assertFalse(w.controller.TryStartTitanOrbit())
        w.cadet.LeftHookReady = True
        self.assertTrue(w.controller.TryStartTitanOrbit())
        self.assertEqual(w.controller._state, "OrbitAttach")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertTrue(any("orbit_launch" in x for x in w.messages))

    def test_arc_uses_physical_hook_and_sideways_motion_then_releases(self):
        w = self.setup_close_orbit("Right")
        w.controller.PlanApproach()
        self.assertEqual(w.controller._state, "OrbitAttach")
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.tick()
        self.assertEqual(w.controller._state, "OrbitSwing")
        self.assertIn(("gas", True), w.cadet.calls)
        w.tick()
        moves = [x for x in w.cadet.calls if x[0] == "move"]
        self.assertTrue(moves)
        self.assertGreater(moves[-1][1].X, 0)
        w.cadet.Position = Vector(15, 8, 25)
        w.tick(1.6)
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertFalse(w.cadet.IsHookedLeft)
        self.assertTrue(any("orbit_end" in x and "radial_cross=" in x for x in w.messages))

    def test_left_and_right_styles_select_opposite_tangents(self):
        directions = []
        for style in ("Left", "Right"):
            w = self.setup_close_orbit(style)
            w.controller.PlanApproach()
            w.cadet.IsHookedLeft = True
            w.cadet.LeftHookPosition = w.titan.NapePosition
            w.tick()
            w.tick()
            directions.append([x[1] for x in w.cadet.calls if x[0] == "move"][-1])
        self.assertLess(directions[0].X, 0)
        self.assertGreater(directions[1].X, 0)

    def test_wrong_hook_attachment_and_hold_release_arc(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = Vector(500, 40, 500)
        w.tick()
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertFalse(w.cadet.IsHookedLeft)
        self.assertTrue(any("attachment_not_near_nape" in x for x in w.messages))
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.tick()
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertFalse(w.cadet.IsHookedLeft)
        self.assertFalse(w.cadet.attacking)

    def test_attack_window_is_checked_during_first_traversal_leg(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller._traverseMode = "approach"
        w.controller.Enter("TraverseBurst", "test")
        w.cadet.IsHookedLeft = True
        w.cadet.Position = w.titan.NapePosition
        w.tick()
        self.assertEqual(w.controller._state, "AttackSetup")
        self.assertFalse(w.cadet.IsHookedLeft)
        w.tick()
        self.assertEqual(w.controller._state, "Strike")
        self.assertIn(("attack", True), w.cadet.calls)

    def test_blocked_nape_and_wrong_orders_do_not_attack_in_flight(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller._traverseMode = "approach"
        w.controller.Enter("TraverseAttach", "test")
        w.cadet.Position = w.titan.NapePosition
        w.hit = NS(Point=Vector(0, 8, 41), Distance=1.0)
        w.tick()
        self.assertEqual(w.controller._state, "TraverseAttach")
        self.assertNotIn(("attack", True), w.cadet.calls)
        w.hit = None
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertNotIn(("attack", True), w.cadet.calls)

    def test_hook_cooldown_does_not_immediately_abandon_target(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.cadet.LeftHookReady = False
        w.controller.PlanApproach()
        self.assertEqual(w.controller._state, "WaitHook")
        w.tick(1.0)
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        w.cadet.LeftHookReady = True
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")

    def test_attack_observation_waits_for_delayed_damage_callback(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.controller.AcquireTarget()
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        w.cadet.State = "Attack"
        w.cadet.CurrentAnimation = "attack"
        w.tick(0.31)
        self.assertEqual(w.controller._state, "VerifyAttack")
        self.assertTrue(any("attack_state_observed" in x for x in w.messages))
        w.tick(0.5)
        self.assertFalse(any("attack_result" in x for x in w.messages))
        w.controller.OnCharacterDamaged(w.titan, w.cadet, "cadet", 100)
        w.tick()
        self.assertTrue(any("confirmed_damage=true" in x and "by_cadet=True" in x for x in w.messages))
        self.assertEqual(w.controller._state, "Retreat")

    def test_lost_target_interrupts_orbit_without_attack(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.titans.items.clear()
        w.tick()
        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertFalse(w.cadet.attacking)
        self.assertIn(("release_left",), w.cadet.calls)

    def test_combat_arc_off_falls_back_to_map_traversal(self):
        w = self.setup_close_orbit("Off")
        self.assertFalse(w.controller.TryStartTitanOrbit())
        self.assertNotIn("OrbitAttach", w.controller._state)
        self.assertFalse(any(x[0] == "launch" for x in w.cadet.calls))

    def test_orbit_attachment_lost_aborts_and_waits_for_hook_retraction(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.tick()
        w.cadet.LeftHookPosition = Vector(500, 40, 500)
        w.tick()
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertFalse(w.cadet.IsHookedLeft)
        self.assertTrue(any("attachment_moved_away_from_nape" in x for x in w.messages))
        w.cadet.LeftHookReady = True
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_attack_timeout_reports_no_damage_without_fabricating_swing(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.controller.AcquireTarget()
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        w.tick(0.31)
        w.tick(1.1)
        result = [x for x in w.messages if "event=attack_result" in x][-1]
        self.assertIn("confirmed_damage=false", result)
        self.assertIn("attack_state_observed=False", result)
        self.assertNotIn("confirmed_kill=true", result)

    def test_collision_risk_aborts_arc_before_attacking(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.cadet.Velocity = Vector(0, 0, 10)
        w.hit = NS(Point=Vector(0, 8, 20), Distance=3.0)
        w.tick()
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertTrue(any("orbit_end" in x and "collision_risk" in x for x in w.messages))
        self.assertFalse(w.cadet.attacking)

    def test_alternating_arc_changes_side_after_failed_attempt(self):
        w = self.setup_close_orbit("Alternate")
        self.assertTrue(w.controller.TryStartTitanOrbit())
        self.assertEqual(w.controller._orbitSide, 1.0)
        w.controller.EndOrbit("test")
        w.cadet.LeftHookReady = True
        self.assertTrue(w.controller.TryStartTitanOrbit())
        self.assertEqual(w.controller._orbitSide, -1.0)
        self.assertEqual(w.controller._orbitAttempts, 2)
        w.controller.EndOrbit("test")
        w.cadet.LeftHookReady = True
        self.assertFalse(w.controller.TryStartTitanOrbit())

    def test_arc_attack_window_logs_arc_end_and_attempts_real_attack(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.tick()
        w.cadet.Position = Vector(0, 8, 38)
        w.tick()
        self.assertEqual(w.controller._state, "AttackSetup")
        self.assertTrue(any("orbit_end" in x and "reason=attack_window" in x and "radial_cross=" in x for x in w.messages))
        w.tick()
        self.assertIn(("attack", True), w.cadet.calls)
        attempt = [x for x in w.messages if "event=attack_attempt" in x][-1]
        self.assertIn("human_state=", attempt)
        self.assertIn("target_forward=", attempt)

    def test_orbit_low_gas_preempts_hooks_and_resumes_mission(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.tick()
        w.cadet.CurrentGas = 20
        w.tick()
        self.assertEqual(w.controller._state, "SeekSupply")
        self.assertEqual(w.controller._resumeAfterSupply, "Engage")
        self.assertFalse(w.cadet.IsHookedLeft)

    def test_wrong_character_and_missing_titan_never_launch_titan_arc(self):
        w = self.setup_close_orbit()
        w.sphere_hit = NS(Type="Human")
        self.assertFalse(w.controller.TryStartTitanOrbit())
        w.sphere_hit = None
        self.assertFalse(w.controller.TryStartTitanOrbit())
        self.assertFalse(any(x[0] == "launch" for x in w.cadet.calls))
        self.assertEqual(w.controller._orbitAttempts, 0)

    def test_hook_wait_timeout_and_hold_do_not_start_attack(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.cadet.LeftHookReady = False
        w.controller.PlanApproach()
        self.assertEqual(w.controller._state, "WaitHook")
        w.tick(2.1)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        w.controller.Enter("WaitHook", "test")
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertFalse(w.cadet.attacking)

    def test_airborne_recovery_waits_for_retracting_hook_and_retains_target(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.cadet.Grounded = False
        w.cadet.LeftHookReady = False
        w.controller._lastFailureReason = "collision_risk"
        w.controller.Enter("Recover", "test")
        w.tick()
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertNotEqual(w.controller._bannedTargetViewId, w.titan.ViewID)
        w.cadet.LeftHookReady = True
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_airborne_recovery_hook_wait_remains_bounded(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.cadet.Grounded = False
        w.cadet.LeftHookReady = False
        w.controller._lastFailureReason = "collision_risk"
        w.controller.Enter("Recover", "test")
        w.tick()
        w.tick(2.1)
        self.assertEqual(w.controller._state, "Recover")
        w.tick()
        self.assertEqual(w.controller._state, "Explore")
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)

    def test_successful_reposition_refreshes_approach_not_recovery_budget(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.MaxTraversePerTarget = 2
        w.controller._targetTraverseCount = 2
        w.controller._targetRecoveries = 1
        w.controller._orbitAttempts = 2
        w.controller._groundRecoveryAttempt = 1
        w.controller._groundRecoveryTargetId = w.titan.ViewID
        w.controller._groundRecoveryStartPosition = Vector(4, 0, 0)
        w.controller._groundRecoveryStartDistance = w.controller.GroundDistanceToTarget()
        w.controller._groundRecoveryGoal = Vector(20, 0, 0)
        w.controller._groundRecoveryActive = True
        w.controller._groundGoal = Vector(20, 0, 0)
        w.cadet.Position = Vector(20, 0, 0)
        w.controller.Enter("RecoverGround", "test")
        w.tick()
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertEqual(w.controller._targetTraverseCount, 0)
        self.assertEqual(w.controller._targetRecoveries, 1)
        self.assertEqual(w.controller._orbitAttempts, 0)
        self.assertTrue(any("approach_budget_refreshed" in m for m in w.messages))
        w.tick()
        self.assertNotEqual(w.controller._state, "Recover")

    def test_retreat_and_patrol_do_not_consume_titan_approach_budget(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        for mode in ("retreat", "explore", "supply"):
            w.controller._traverseMode = mode
            w.controller._trOutcome = "completed"
            w.controller._trStartPosition = w.cadet.Position
            before = w.controller._targetTraverseCount
            w.controller.FinishTraverse()
            self.assertEqual(w.controller._targetTraverseCount, before)

    def test_map_blocked_attack_setup_falls_back_without_swing(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.controller.AcquireTarget()
        w.hit = NS(Point=Vector(0, 8, 41), Distance=1.0)
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        self.assertEqual(w.controller._state, "Recover")
        self.assertNotIn(("attack", True), w.cadet.calls)
        self.assertTrue(any("attack_blocked" in x for x in w.messages))

    def test_collision_check_has_priority_over_in_flight_attack(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.cadet.Position = w.titan.NapePosition
        w.cadet.Velocity = Vector(0, 0, 10)
        w.hit = NS(Point=Vector(0, 8, 43), Distance=1.0)
        w.tick()
        self.assertEqual(w.controller._state, "WaitHook")
        self.assertNotIn(("attack", True), w.cadet.calls)
        self.assertTrue(any("collision_probe" in m and "hit_distance=" in m for m in w.messages))

    def test_other_actor_damage_does_not_end_window_before_cadet_callback(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.controller.AcquireTarget()
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        w.tick(0.31)
        w.controller.OnCharacterDamaged(w.titan, NS(ViewID=999), "other", 20)
        w.tick(0.2)
        self.assertEqual(w.controller._state, "VerifyAttack")
        w.controller.OnCharacterDamaged(w.titan, w.cadet, "cadet", 100)
        w.tick()
        self.assertTrue(any("confirmed_damage=true" in x and "by_cadet=True" in x for x in w.messages))

    def test_other_actor_damage_is_not_credited_to_cadet(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.controller.AcquireTarget()
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        w.tick(0.31)
        w.controller.OnCharacterDamaged(w.titan, NS(ViewID=999), "other", 20)
        w.tick(1.1)
        self.assertTrue(any("confirmed_damage=true" in x and "by_cadet=False" in x for x in w.messages))
        self.assertEqual(w.controller._state, "Retreat")

    def test_close_intercept_keeps_tether_until_strike_commit_range(self):
        w = self.setup_close_orbit()
        w.controller.PlanApproach()
        w.cadet.IsHookedLeft = True
        w.cadet.LeftHookPosition = w.titan.NapePosition
        w.tick()
        w.cadet.Position = Vector(0, 8, 34)
        w.tick()
        self.assertEqual(w.controller._state, "OrbitSwing")
        self.assertNotIn(("attack", True), w.cadet.calls)
        movement = [x[1] for x in w.cadet.calls if x[0] == "move"][-1]
        self.assertGreater(movement.Z, 0.8)
        self.assertTrue(any("orbit_intercept" in x for x in w.messages))
        w.cadet.Position = Vector(0, 8, 38)
        w.tick()
        self.assertEqual(w.controller._state, "AttackSetup")

    def test_wall_escape_can_back_away_when_forward_and_sides_are_blocked(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 100)
        w.titan.NapePosition = Vector(4, 8, 100)
        w.controller.AcquireTarget()
        w.hit = lambda start, end, layer: NS(Point=end, Distance=2) if end.Z >= start.Z else None
        w.controller.Enter("Recover", "test")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertLess(w.controller._groundGoal.Z, w.cadet.Position.Z)
        self.assertTrue(any("escape_route candidate=4" in x for x in w.messages))
        self.assertTrue(any(x[0] == "move" for x in w.cadet.calls))

    def test_failed_escape_tries_one_alternate_route_then_pauses_if_still_stuck(self):
        w = World()
        w.tick()
        w.controller.Persistence = 3
        self.assertEqual(w.controller.RecoveryBudget(), 2)
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test")
        w.tick()
        first_goal = w.controller._groundGoal
        first_side = w.controller._groundRecoverySelectedSide
        self.assertEqual(w.controller._targetRecoveries, 1)

        w.tick(6.1)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(w.controller._targetRecoveries, 1)
        self.assertEqual(w.controller._bannedTargetViewId, 0)
        first_end = next(x for x in w.messages if "event=reposition_end" in x)
        self.assertIn("run=", first_end)
        self.assertIn("cadet=AICadetsM2-1", first_end)
        self.assertIn("target_id=101", first_end)
        self.assertIn("order_seq=", first_end)
        self.assertIn("attempt=1", first_end)
        self.assertIn("start_pos=", first_end)
        self.assertIn("end_pos=", first_end)
        self.assertIn("moved=", first_end)
        self.assertIn("movement_result=moved<2", first_end)
        self.assertIn("goal=", first_end)
        self.assertIn("target_gain=", first_end)
        self.assertIn("ai_state=Idle", first_end)
        self.assertIn("termination_reason=timeout", first_end)
        route_records = [x for x in w.messages if "event=escape_route" in x]
        self.assertEqual(len(route_records), 1)
        self.assertIn("attempt=1", route_records[0])
        self.assertFalse(any("event=reposition_retry" in x for x in w.messages))

        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        second_goal = w.controller._groundGoal
        self.assertNotEqual(second_goal, first_goal)
        self.assertEqual(w.controller._groundRecoverySelectedSide, -first_side)
        self.assertEqual(w.controller._targetRecoveries, 2)
        retry = next(x for x in w.messages if "event=reposition_retry" in x)
        self.assertIn("target_id=101", retry)
        self.assertIn("attempt=2", retry)
        self.assertIn("opposite_side=true", retry)
        self.assertIn("first_goal=", retry)
        self.assertIn("goal=", retry)
        route_records = [x for x in w.messages if "event=escape_route" in x]
        self.assertEqual(len(route_records), 2)
        self.assertIn("attempt=2", route_records[1])
        self.assertIn("candidate=6", route_records[1])

        w.tick(6.1)
        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)
        self.assertTrue(any("escape_no_displacement" in x for x in w.messages))
        self.assertEqual(len([x for x in w.messages if "event=reposition_start" in x]), 2)

    def test_odm_transition_under_two_units_waits_grounded_then_retries_opposite_side_once(self):
        w = World()
        w.tick()
        w.controller.Persistence = 3
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_odm_under_displacement")
        w.tick()
        first_goal = w.controller._groundGoal
        first_side = w.controller._groundRecoverySelectedSide
        self.assertEqual(w.controller._state, "RecoverGround")

        w.cadet.Grounded = False
        w.tick()
        self.assertEqual(w.controller._state, "Recover")
        self.assertTrue(w.controller._groundRecoveryRetryRequested)
        first_end = next(line for line in w.messages if "event=reposition_end" in line)
        self.assertIn("movement_result=moved<2", first_end)
        self.assertIn("termination_reason=odm_transition", first_end)
        move_calls = movement_request_count(w.cadet)

        w.tick(0.5)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(movement_request_count(w.cadet), move_calls)

        w.cadet.Grounded = True
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertEqual(w.controller._groundRecoverySelectedSide, -first_side)
        self.assertNotEqual(w.controller._groundGoal, first_goal)
        retries = [line for line in w.messages if "event=reposition_retry " in line]
        self.assertEqual(len(retries), 1)
        self.assertIn("target_id=101", retries[0])
        self.assertIn("attempt=2", retries[0])
        self.assertIn("opposite_side=true", retries[0])

    def test_second_odm_under_displacement_bans_target_without_a_third_retry(self):
        w = World()
        w.tick()
        w.controller.Persistence = 3
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_second_odm_under_displacement")
        w.tick()
        w.cadet.Grounded = False
        w.tick()
        self.assertTrue(w.controller._groundRecoveryRetryRequested)

        w.cadet.Grounded = True
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        move_calls_before_second_end = movement_request_count(w.cadet)
        w.cadet.Grounded = False
        w.tick()

        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)
        self.assertEqual(movement_request_count(w.cadet), move_calls_before_second_end)
        self.assertEqual(len([line for line in w.messages if "event=reposition_retry " in line]), 1)
        self.assertEqual(len([line for line in w.messages if "event=reposition_start" in line]), 2)

    def test_second_odm_recovery_records_same_target_progress_before_leaving_ground(self):
        w = World()
        w.tick()
        w.controller.Persistence = 3
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_retry_progress_at_odm_transition")
        w.tick()
        w.cadet.Grounded = False
        w.tick()
        w.cadet.Grounded = True
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")

        w.cadet.Position = w.cadet.Position + Vector(0, 0, 3)
        w.cadet.Grounded = False
        w.tick()

        self.assertFalse(w.controller._groundRecoveryRetryProgressPending)
        progress = next(line for line in w.messages if "event=reposition_retry_progress " in line)
        self.assertIn("target_id=101", progress)
        self.assertIn("target_gain=", progress)
        self.assertIn("termination_reason=same_target_progress_confirmed_after_odm_transition", progress)

    def test_hold_cancels_a_deferred_ground_recovery_retry(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_hold_cancels_deferred_retry")
        w.tick()
        w.cadet.Grounded = False
        w.tick()
        self.assertTrue(w.controller._groundRecoveryRetryRequested)
        move_calls = movement_request_count(w.cadet)

        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertFalse(w.controller._groundRecoveryRetryRequested)
        w.cadet.Grounded = True
        w.tick()
        self.assertEqual(movement_request_count(w.cadet), move_calls)
        self.assertFalse(any("event=reposition_retry " in line for line in w.messages))

    def test_deferred_retry_landing_wait_times_out_safely(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_retry_landing_timeout")
        w.tick()
        w.cadet.Grounded = False
        w.tick()
        move_calls = movement_request_count(w.cadet)

        w.tick(4.1)

        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)
        self.assertFalse(w.controller._groundRecoveryRetryRequested)
        self.assertEqual(movement_request_count(w.cadet), move_calls)
        self.assertTrue(any("event=reposition_retry_abandoned" in line
                            and "ground_wait_timeout" in line
                            and "command_dispatched=false" in line for line in w.messages))

    def test_lost_target_cancels_a_deferred_retry(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_retry_target_loss")
        w.tick()
        w.cadet.Grounded = False
        w.tick()
        self.assertTrue(w.controller._groundRecoveryRetryRequested)
        move_calls = movement_request_count(w.cadet)
        w.titan.IsAlive = False

        w.tick()

        self.assertEqual(w.controller._state, "AcquireTarget")
        self.assertFalse(w.controller._groundRecoveryRetryRequested)
        self.assertEqual(movement_request_count(w.cadet), move_calls)
        self.assertTrue(any("event=reposition_retry_cancelled" in line
                            and "termination_reason=retry_target_lost" in line for line in w.messages))

    def test_authority_loss_ends_active_recovery_with_a_reasoned_record(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_authority_loss_recovery")
        w.tick()
        self.assertTrue(w.controller._groundRecoveryActive)

        w.network.IsMasterClient = False
        w.tick()

        self.assertEqual(w.controller._state, "Done")
        ended = next(line for line in w.messages if "event=reposition_end" in line)
        self.assertIn("termination_reason=termination_master_lost_cleanup_unavailable", ended)
        self.assertIn("target_id=101", ended)
        self.assertIn("start_pos=", ended)
        self.assertIn("end_pos=", ended)
        self.assertIn("moved=", ended)
        self.assertIn("goal=", ended)
        self.assertIn("target_gain=", ended)
        self.assertIn("ai_state=", ended)

    def test_opposite_retry_uses_shorter_clear_goal_when_full_corridors_are_blocked(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_shorter_opposite_goal")
        w.tick()
        first_goal = w.controller._groundGoal
        first_side = w.controller._groundRecoverySelectedSide
        self.assertEqual(first_side, 1)

        w.hit = lambda start, end, layer: (
            NS(Point=end, Distance=2)
            if ((end.X - start.X) ** 2 + (end.Z - start.Z) ** 2) ** 0.5 > 10.0 else None)
        w.tick(6.1)
        self.assertEqual(w.controller._state, "Recover")
        w.tick()

        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertEqual(w.controller._groundRecoverySelectedSide, -first_side)
        self.assertEqual(w.controller._groundRecoverySelectedScale, 0.75)
        self.assertNotEqual(w.controller._groundGoal, first_goal)
        retry = next(x for x in w.messages if "event=reposition_retry" in x)
        self.assertIn("opposite_side=true", retry)
        self.assertIn("scale=0.75", retry)
        self.assertNotIn("goal=none", retry)

        w.tick(6.1)
        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(len([x for x in w.messages if "event=reposition_start" in x]), 2)

    def test_blocked_opposite_retry_is_reported_without_claiming_a_command(self):
        w = World()
        w.tick()
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_blocked_opposite_retry")
        w.tick()
        move_calls_before_retry = movement_request_count(w.cadet)
        w.hit = NS(Point=Vector(4, 1, 3), Distance=3.0)

        w.tick(6.1)
        self.assertEqual(w.controller._state, "Recover")
        w.tick()

        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(movement_request_count(w.cadet), move_calls_before_retry)
        self.assertTrue(any("event=reposition_retry_blocked" in line
                            and "command_dispatched=false" in line for line in w.messages))
        self.assertFalse(any("event=reposition_retry " in line for line in w.messages))
        self.assertEqual(len([line for line in w.messages if "event=reposition_start" in line]), 1)

    def test_opposite_retry_can_use_back_diagonal_when_other_opposite_routes_are_blocked(self):
        w = World()
        w.tick()
        w.controller.Persistence = 3
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_opposite_back_diagonal_retry")
        w.tick()
        first_goal = w.controller._groundGoal
        first_side = w.controller._groundRecoverySelectedSide
        self.assertEqual(first_side, 1)

        w.tick(6.1)
        self.assertEqual(w.controller._state, "Recover")
        first_end = next(x for x in w.messages if "event=reposition_end" in x)
        self.assertIn("movement_result=moved<2", first_end)

        def block_except_opposite_back_diagonal(start, end, layer):
            to_target = w.titan.Position - w.cadet.Position
            distance = (to_target.X * to_target.X + to_target.Z * to_target.Z) ** 0.5
            forward_x = to_target.X / distance
            forward_z = to_target.Z / distance
            right_x = forward_z
            right_z = -forward_x
            dx = end.X - start.X
            dz = end.Z - start.Z
            forward_amount = dx * forward_x + dz * forward_z
            side_amount = dx * right_x + dz * right_z
            if forward_amount < -4.0 and side_amount < -4.0:
                return None
            return NS(Point=end, Distance=2.0)

        w.hit = block_except_opposite_back_diagonal
        w.tick()

        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        self.assertEqual(w.controller._groundRecoverySelectedCandidate, 6)
        self.assertEqual(w.controller._groundRecoverySelectedSide, -first_side)
        self.assertNotEqual(w.controller._groundGoal, first_goal)
        retry = next(x for x in w.messages if "event=reposition_retry " in x)
        self.assertIn("candidate=6", retry)
        self.assertIn("opposite_side=true", retry)
        self.assertIn("goal=", retry)

    def test_successful_opposite_retry_requires_same_target_progress(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.Enter("Recover", "test_retry_progress")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        w.tick(6.1)
        self.assertEqual(w.controller._state, "Recover")
        w.tick()
        self.assertEqual(w.controller._state, "RecoverGround")
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)
        retry_goal = w.controller._groundGoal
        w.cadet.Position = retry_goal
        w.tick(0.02)
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertTrue(w.controller._groundRecoveryRetryProgressPending)

        w.controller.StartGroundApproach(False)
        self.assertEqual(w.controller._state, "ApproachGround")
        w.cadet.Position = w.cadet.Position + Vector(0, 0, 10)
        w.tick(5.1)
        self.assertEqual(w.controller._state, "ApproachGround")
        self.assertFalse(w.controller._groundRecoveryRetryProgressPending)
        progress = next(x for x in w.messages if "event=reposition_retry_progress" in x)
        self.assertIn("target_id=101", progress)
        self.assertIn("attempt=2", progress)
        self.assertIn("target_gain=", progress)
        self.assertIn("termination_reason=same_target_progress_confirmed", progress)

    def test_tactic_catalog_matches_runtime_capabilities_and_fails_closed(self):
        import json
        catalog = json.loads((Path(__file__).resolve().parents[1] / "docs/M2_TACTIC_CATALOG.json").read_text())
        down_strike = catalog["special_approaches"][0]
        self.assertEqual(down_strike["required_special"], "DownStrike")
        self.assertEqual(down_strike["capability"], "definition_only")
        self.assertIn("physical_activation_validated", down_strike["requirements"])
        w = World()
        w.tick()
        for tactic in catalog["tactics"]:
            self.assertEqual(w.controller.TacticCapability(tactic["id"]), tactic["capability"])
            accepted = w.controller.SelectCombatTactic(tactic["id"])
            self.assertEqual(accepted, tactic["capability"] == "physical_experimental")
        self.assertEqual(w.controller._combatTactic, "NapeStrike")
        self.assertFalse(w.controller.SelectCombatTactic("UnverifiedTactic"))
        self.assertEqual(w.controller._combatTactic, "NapeStrike")

    def test_attack_waits_for_landing_state_to_clear(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.cadet.State = "Land"
        w.controller.AcquireTarget()
        w.controller.Enter("AttackSetup", "test")
        w.tick()
        self.assertEqual(w.controller._state, "AttackSetup")
        self.assertNotIn(("attack", True), w.cadet.calls)
        self.assertTrue(any("attack_wait_ready" in x for x in w.messages))
        w.cadet.State = "Idle"
        w.tick(0.1)
        self.assertEqual(w.controller._state, "Strike")
        self.assertIn(("attack", True), w.cadet.calls)

    def test_attack_readiness_timeout_and_hold_are_bounded(self):
        w = World()
        w.tick()
        w.cadet.Position = w.titan.NapePosition
        w.cadet.State = "Land"
        w.controller.AcquireTarget()
        w.controller.Enter("AttackSetup", "test")
        w.tick(0.9)
        self.assertEqual(w.controller._state, "Recover")
        self.assertNotIn(("attack", True), w.cadet.calls)
        w.controller.Enter("AttackSetup", "test_hold")
        w.persistent.update({"AICadetsCmdSequence": 1, "AICadetsCmdMode": "Hold", "AICadetsCmdScope": "all"})
        w.tick()
        self.assertEqual(w.controller._state, "Hold")
        self.assertNotIn(("attack", True), w.cadet.calls)

    def test_circle_does_not_ban_target_before_bounded_recovery(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 0, 600)
        w.titan.NapePosition = Vector(4, 8, 602)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        for position in (Vector(14, 0, 0), Vector(14, 0, 10), Vector(4, 0, 10), Vector(4, 0, 0)):
            w.cadet.Position = position
            w.tick(1.0)
        w.tick(1.1)
        self.assertEqual(w.controller._state, "Recover")
        self.assertEqual(w.controller._bannedTargetViewId, 0)
        self.assertEqual(w.controller._targetViewId, w.titan.ViewID)

    def test_ground_fallback_uses_projected_goal_and_planar_arrival_despite_nape_height(self):
        w = World()
        w.tick()
        w.cadet.Position = Vector(4, 10, 0)
        w.titan.Position = Vector(4, 10, 100)
        w.titan.NapePosition = Vector(4, 22.5, 100)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(True)
        self.assertEqual(w.controller._groundGoal, Vector(4, 10, 100))
        self.assertFalse(any(call[0] == "move_to_target" for call in w.cadet.calls))
        self.assertTrue(any("arrival_radius=18.0" in m and "request=Human.Move" in m and "acceptance=not_exposed" in m for m in w.messages))

        # The ground arrival is reachable in XZ even though the nape remains
        # more than the 5-unit strike range above the cadet.
        w.cadet.Position = Vector(4, 10, 83)
        nape_distance = Vector.Distance(w.cadet.Position, w.titan.NapePosition)
        self.assertGreater(nape_distance, w.controller.EffectiveStrikeRange())
        w.tick(0.02)
        self.assertEqual(w.controller._state, "PlanApproach")
        self.assertTrue(any("motion_segment_done" in m and "planar_distance=17" in m and "arrival_radius=18" in m for m in w.messages))

    def test_engine_comparison_also_uses_a_reachable_ground_goal(self):
        w = World()
        w.tick()
        w.cadet.Position = Vector(4, 10, 0)
        w.titan.Position = Vector(4, 10, 100)
        w.titan.NapePosition = Vector(4, 22.5, 100)
        w.controller.GroundSteering = "Engine"
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(True)
        call = [c for c in w.cadet.calls if c[0] == "move_to"][-1]
        self.assertEqual(call[1], Vector(4, 10, 100))
        self.assertEqual(call[2], 18.0)
        self.assertFalse(any(c[0] == "move_to_target" for c in w.cadet.calls))
        self.assertTrue(any("request=Human.MoveTo" in m and "api_return=void" in m and "ai_state_after=MoveTo" in m for m in w.messages))

    def test_engine_ground_goal_refreshes_when_titan_moves(self):
        w = World()
        w.tick()
        w.cadet.Position = Vector(4, 10, 0)
        w.titan.Position = Vector(4, 10, 100)
        w.titan.NapePosition = Vector(4, 22.5, 100)
        w.controller.GroundSteering = "Engine"
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        before = len([c for c in w.cadet.calls if c[0] == "move_to"])

        w.titan.Position = Vector(4, 10, 110)
        w.titan.NapePosition = Vector(4, 22.5, 110)
        w.tick(0.02)

        moves = [c for c in w.cadet.calls if c[0] == "move_to"]
        self.assertEqual(len(moves), before + 1)
        self.assertEqual(moves[-1][1], Vector(4, 10, 110))

    def test_direct_ground_steering_is_repeatable_for_stationary_titan_and_closes_planarly(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 10, 100)
        w.titan.NapePosition = Vector(4, 22.5, 100)
        w.cadet.Position = Vector(4, 10, 0)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        first = [c[1] for c in w.cadet.calls if c[0] == "move"][-1]
        for _ in range(3):
            w.tick(0.02)
        repeated = [c[1] for c in w.cadet.calls if c[0] == "move"][-3:]
        self.assertTrue(all(direction == first for direction in repeated))

        w.cadet.Position = Vector(4, 10, 10)
        w.tick(5.0)
        progress = [m for m in w.messages if "event=pursuit_progress" in m][-1]
        self.assertIn("distance=90", progress)
        self.assertIn("target_gain=10", progress)
        self.assertEqual(w.controller._groundStalledChecks, 0)

    def test_moving_titan_distance_is_measured_relative_to_its_ground_position(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(4, 10, 100)
        w.titan.NapePosition = Vector(4, 22.5, 100)
        w.cadet.Position = Vector(4, 10, 0)
        w.controller.AcquireTarget()
        w.controller.StartGroundApproach(False)
        w.cadet.Position = Vector(4, 10, 10)
        w.titan.Position = Vector(4, 10, 110)
        w.titan.NapePosition = Vector(4, 22.5, 110)
        w.tick(5.0)
        progress = [m for m in w.messages if "event=pursuit_progress" in m][-1]
        self.assertIn("distance=100", progress)
        self.assertIn("target_gain=0", progress)
        self.assertEqual(w.controller._groundStalledChecks, 0)

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
        self.assertEqual(w.controller._state, "Observe")
        self.assertEqual(w.controller._bannedTargetViewId, w.titan.ViewID)


if __name__ == "__main__":
    unittest.main()
