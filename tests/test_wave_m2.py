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
        self.IsAlive = self.IsMine = self.LeftHookEnabled = self.LeftHookReady = True
        self.IsHookedLeft = False
        self.Grounded = True
        self.ViewID = 777
        self.Name = "Levi"
        self.attacking = False
        self.calls = []

    def SetDisplayName(self, name, tag):
        self.calls.append(("name", name, tag))

    def Idle(self):
        self.calls.append(("idle",))

    def AimAt(self, position):
        self.calls.append(("aim", position))

    def Move(self, direction):
        self.calls.append(("move", direction))

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

    def test_low_gas_terminates_safely(self):
        w = World()
        w.tick()
        w.cadet.CurrentGas = 2.0
        w.tick()
        self.assertEqual(w.controller._state, "Done")
        self.assertTrue(any("insufficient_odm_resources" in m for m in w.messages))

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

    def test_distant_target_dispatches_a_hook_approach(self):
        w = World()
        w.tick()
        w.titan.Position = Vector(0, 0, 600)
        w.titan.NapePosition = Vector(0, 8, 602)
        w.hit = NS(Point=Vector(4, 20, 48), Distance=46.0)
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        w.tick()
        self.assertEqual(w.controller._state, "TraverseAttach")
        self.assertTrue(any(action[0] == "launch" for action in w.cadet.calls))

    def test_empty_roster_is_reported_and_throttled(self):
        w = World()
        w.tick()
        w.titans.items.clear()
        w.controller.Enter("AcquireTarget", "test")
        w.tick()
        self.assertEqual(w.controller._state, "Regroup")
        self.assertTrue(any("reason=no_alive_titans listed=0 alive=0" in m for m in w.messages))
        w.tick(0.4)
        self.assertEqual(w.controller._state, "Regroup")
        w.tick(2.2)
        self.assertEqual(w.controller._state, "AcquireTarget")

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
        self.assertEqual(w.controller._state, "Explore")
        self.assertTrue(any(a[0] == "move" for a in w.cadet.calls))

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
        self.assertEqual(w.controller._state, "AcquireTarget")

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
