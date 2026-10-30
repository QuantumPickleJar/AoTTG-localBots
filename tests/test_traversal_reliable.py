"""Source-driven tests for AICadetsTraversalReliable.cl with mocked observations."""
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from cl_harness import Vector, load_controller

SOURCE = (Path(__file__).resolve().parents[1] / "addons" / "AICadetsTraversalReliable.cl").read_text()


class Scout:
    def __init__(self):
        self.Position = Vector(4, 0, 0)
        self.Velocity = Vector(0, 0, 0)
        self.CurrentGas = 100.0
        self.IsAlive = self.IsMine = self.LeftHookEnabled = self.LeftHookReady = True
        self.IsHookedLeft = False
        self.Name = "Levi"
        self.gas = False
        self.calls = []

    def SetDisplayName(self, name, tag):
        self.calls.append(("name", name, tag))

    def Idle(self):
        self.calls.append(("idle",))

    def AimAt(self, position):
        self.calls.append(("aim", position))

    def Jump(self):
        self.calls.append(("jump",))

    def LaunchHookLeft(self, position):
        self.LeftHookReady = False
        self.calls.append(("launch", position))

    def UseGas(self, enabled):
        self.gas = enabled
        self.calls.append(("gas", enabled))

    def ReleaseHookLeft(self):
        self.IsHookedLeft = False
        self.calls.append(("release_left",))

    def ReleaseHookRight(self):
        self.calls.append(("release_right",))


class World:
    def __init__(self):
        self.scout = Scout()
        self.time = NS(GameTime=0.0)
        self.host = NS(
            Character=NS(Type="Human", IsAlive=True, Position=Vector(0, 0, 0), Forward=Vector(0, 0, 1), Right=Vector(1, 0, 0))
        )
        self.network = NS(IsMasterClient=True, MyPlayer=self.host)
        self.messages = []
        self.spawns = 0
        self.humans = []
        self.hit = None
        self.casts = []
        self.controller = load_controller(
            {
                "Vector3": Vector,
                "Time": self.time,
                "Network": self.network,
                "Game": NS(SpawnHumanAt=self.spawn, AIHumans=self.humans, Print=self.messages.append),
                "Physics": NS(LineCast=self.cast),
                "Convert": NS(ToString=str),
                "LoadoutEnum": NS(HumanBlades="Blades"),
                "CollideWithEnum": NS(MapObjects="map", MapEditor="editor"),
            },
            SOURCE,
        )
        self.controller.OnGameStart()

    def spawn(self, costume, name, loadout, position, rotation):
        self.spawns += 1
        self.humans.append(self.scout)
        return self.scout

    def cast(self, start, end, layer):
        self.casts.append((start, end, layer))
        if callable(self.hit):
            return self.hit(start, end, layer)
        return self.hit

    def tick(self, dt=0.02):
        self.time.GameTime += dt
        self.controller.OnTick()

    def setup_leg1_launch(self):
        self.tick()
        self.hit = NS(Point=Vector(4, 16, 45), Distance=46.0)
        self.tick(1.01)
        self.assert_state("Attach")
        self.hit = None

    def attach(self):
        self.scout.IsHookedLeft = True
        self.tick()

    def assert_state(self, state):
        assert self.controller._state == state, (self.controller._state, self.messages[-3:])


class TraversalReliableTests(unittest.TestCase):
    def assert_done(self, world, result_class, reason):
        self.assertEqual(world.controller._state, "Done")
        self.assertFalse(world.scout.gas)
        self.assertIn(("release_left",), world.scout.calls)
        self.assertIn(("release_right",), world.scout.calls)
        self.assertTrue(any("result_class=" + result_class in m for m in world.messages), world.messages)
        self.assertTrue(any("result_reason=" + reason in m for m in world.messages), world.messages)
        before = list(world.scout.calls)
        for _ in range(10):
            world.tick(1)
        self.assertEqual(before, world.scout.calls)

    def test_two_anchors_complete_without_recovery(self):
        w = World()
        w.setup_leg1_launch()
        w.attach()
        self.assertEqual(w.controller._state, "Burst")
        w.scout.Position = Vector(4, 8, 20)
        w.scout.Velocity = Vector(28, 0, 0)
        w.scout.CurrentGas = 99.4
        w.tick(0.61)
        self.assertEqual(w.controller._state, "Coast")
        w.scout.LeftHookReady = True
        w.hit = lambda a, b, layer: NS(Point=Vector(44, 24, 20), Distance=43) if Vector.Distance(a, b) > 25 else None
        w.tick(0.13)
        self.assertEqual(w.controller._state, "Attach")
        w.hit = None
        w.attach()
        self.assertEqual(w.controller._state, "Burst")
        w.scout.Position = Vector(20, 12, 20)
        w.scout.CurrentGas = 98.9
        w.tick(0.61)
        self.assertEqual(w.controller._state, "Observe")
        w.tick(2.01)
        self.assert_done(w, "success", "completed")
        self.assertEqual((w.spawns, w.controller._attempts, w.controller._attachments), (1, 2, 2))

    def test_second_leg_failure_enters_recovery_and_completes(self):
        w = World()
        w.setup_leg1_launch()
        w.attach()
        w.scout.Position = Vector(4, 8, 20)
        w.scout.Velocity = Vector(24, 0, 0)
        w.tick(0.61)
        self.assertEqual(w.controller._state, "Coast")
        w.scout.LeftHookReady = True
        w.hit = None
        w.tick(0.13)
        self.assertEqual(w.controller._state, "RecoverPlan")
        w.hit = lambda a, b, layer: NS(Point=Vector(30, 30, 20), Distance=36) if Vector.Distance(a, b) > 25 else None
        w.tick()
        self.assertEqual(w.controller._state, "RecoverAttach")
        w.hit = None
        w.attach()
        self.assertEqual(w.controller._state, "RecoverBurst")
        w.scout.Position = Vector(18, 16, 20)
        w.tick(0.36)
        self.assertEqual(w.controller._state, "Observe")
        w.tick(2.01)
        self.assert_done(w, "success", "completed_with_recovery")
        self.assertEqual(w.controller._recoveries, 1)

    def test_recovery_stops_safely_when_unavailable(self):
        w = World()
        w.setup_leg1_launch()
        w.attach()
        w.tick(0.61)
        w.scout.LeftHookReady = False
        w.scout.CurrentGas = 2.5
        w.tick(1.01)
        self.assertEqual(w.controller._state, "RecoverPlan")
        w.tick()
        self.assert_done(w, "safe_termination", "recovery_unavailable_resources")

    def test_observe_window_catches_dangerous_fall(self):
        w = World()
        w.setup_leg1_launch()
        w.attach()
        w.scout.Position = Vector(4, 8, 20)
        w.scout.Velocity = Vector(30, 0, 0)
        w.tick(0.61)
        w.scout.LeftHookReady = True
        w.hit = lambda a, b, layer: NS(Point=Vector(44, 24, 20), Distance=43) if Vector.Distance(a, b) > 25 else None
        w.tick(0.13)
        w.hit = None
        w.attach()
        w.tick(0.61)
        self.assertEqual(w.controller._state, "Observe")
        w.scout.LeftHookReady = True
        w.scout.CurrentGas = 40
        w.scout.Velocity = Vector(8, -35, 3)
        w.hit = lambda a, b, layer: NS(Point=Vector(26, 34, 20), Distance=20) if Vector.Distance(a, b) > 25 else None
        w.tick(0.05)
        self.assertEqual(w.controller._state, "RecoverPlan")

    def test_anchor_rejection_and_clearance(self):
        w = World()
        w.tick()
        w.controller._leg = 1
        w.controller._direction = Vector(0, 0, 1)
        w.controller._anchor = None
        # low anchor
        w.hit = NS(Point=Vector(4, 1, 35), Distance=36)
        w.controller.ConsiderAnchor(Vector(0, 0, 1), 12)
        self.assertIsNone(w.controller._anchor)
        # blocked body clearance
        sequence = {"n": 0}

        def cast(start, end, layer):
            sequence["n"] += 1
            if sequence["n"] <= 2:
                return NS(Point=Vector(4, 18, 40), Distance=41)
            return NS(Point=Vector(5, 1, 1), Distance=2)

        w.hit = cast
        w.controller.ConsiderAnchor(Vector(0, 0, 1), 12)
        self.assertIsNone(w.controller._anchor)

    def test_duplicate_guard_and_authority_loss(self):
        w = World()
        w.humans.append(NS(IsAlive=True, Name="AICadetsM1R"))
        w.tick()
        self.assertEqual(w.spawns, 0)
        self.assertTrue(any("existing_scout_restart_lobby" in m for m in w.messages))
        w = World()
        w.setup_leg1_launch()
        w.attach()
        before = list(w.scout.calls)
        w.network.IsMasterClient = False
        w.tick()
        self.assertEqual(before, w.scout.calls)
        self.assertTrue(any("cleanup_unavailable" in m for m in w.messages))

    def test_repeated_start_and_invalid_settings(self):
        w = World()
        w.setup_leg1_launch()
        w.controller.OnGameStart()
        self.assert_done(w, "safe_termination", "repeated_start")
        for key, value in (
            ("HookReach", 200),
            ("RecoveryBurstSeconds", 1.0),
            ("ObserveSeconds", 0.1),
            ("RecoveryAttachTimeout", 10.0),
            ("RecoveryGasReserve", 1.5),
        ):
            w = World()
            setattr(w.controller, key, value)
            w.tick()
            self.assertEqual(w.controller._state, "Done")
            self.assertEqual(w.spawns, 0)
            self.assertTrue(any("invalid_settings" in m for m in w.messages))


if __name__ == "__main__":
    unittest.main()
