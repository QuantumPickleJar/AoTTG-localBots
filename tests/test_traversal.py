"""Exercise the actual .cl branches with mocked observations, never physics."""
import unittest
from types import SimpleNamespace as NS

from cl_harness import Vector, load_controller


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
        self.host = NS(Character=NS(Type="Human", IsAlive=True,
                       Position=Vector(0, 0, 0), Forward=Vector(0, 0, 1),
                       Right=Vector(1, 0, 0)))
        self.network = NS(IsMasterClient=True, MyPlayer=self.host)
        self.messages = []
        self.spawns = 0
        self.humans = []
        self.hit = None
        self.casts = []
        self.controller = load_controller({
            "Vector3": Vector, "Time": self.time, "Network": self.network,
            "Game": NS(SpawnHumanAt=self.spawn, AIHumans=self.humans, Print=self.messages.append),
            "Physics": NS(LineCast=self.cast), "Convert": NS(ToString=str),
            "LoadoutEnum": NS(HumanBlades="Blades"),
            "CollideWithEnum": NS(MapObjects="map", MapEditor="editor"),
        })
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

    def launch(self):
        self.tick()
        # Supply a synthetic map hit only after the spawn clearance check.
        self.hit = NS(Point=Vector(4, 15, 45), Distance=46.0)
        self.tick(1.01)
        assert self.controller._state == "Attach"
        self.hit = None

    def attach(self):
        self.scout.IsHookedLeft = True
        self.tick()
        assert self.controller._state == "Burst"


class TraversalTests(unittest.TestCase):
    def assert_stopped(self, world, reason):
        self.assertEqual(world.controller._state, "Done")
        self.assertFalse(world.scout.gas)
        self.assertIn(("release_left",), world.scout.calls)
        self.assertIn(("release_right",), world.scout.calls)
        self.assertTrue(any("result=" + reason in m for m in world.messages), world.messages)
        before = list(world.scout.calls)
        for _ in range(10):
            world.tick(1)
        self.assertEqual(before, world.scout.calls, "Done must issue no commands")

    def test_two_legs_and_final_metrics(self):
        w = World()
        w.launch()
        w.attach()
        w.scout.Position = Vector(4, 8, 20)
        w.scout.Velocity = Vector(30, 0, 0)
        w.scout.CurrentGas = 99.5
        w.tick(0.61)
        self.assertEqual(w.controller._state, "Coast")
        self.assertFalse(w.scout.gas)
        w.scout.LeftHookReady = True
        # Keep the short collision ray clear, return a distant anchor on long rays.
        w.hit = lambda a, b, layer: NS(Point=Vector(45, 20, 20), Distance=42) if Vector.Distance(a, b) > 30 else None
        w.tick(0.13)
        self.assertEqual(w.controller._state, "Attach")
        self.assertEqual(w.controller._direction, Vector(1, 0, 0))
        w.hit = None
        w.attach()
        w.scout.Position = Vector(25, 12, 20)
        w.scout.CurrentGas = 99.0
        w.tick(0.61)
        self.assertEqual(w.controller._state, "Observe")
        w.tick(1.01)
        self.assert_stopped(w, "completed")
        self.assertEqual((w.spawns, w.controller._attempts, w.controller._attachments), (1, 2, 2))
        self.assertTrue(any("gas_used=1.0" in m for m in w.messages))
        self.assertEqual(sum(c[0] == "jump" for c in w.scout.calls), 1)

    def test_missing_first_or_second_anchor(self):
        for second in (False, True):
            with self.subTest(second=second):
                w = World()
                if second:
                    w.launch()
                    w.attach()
                    w.tick(0.61)
                    w.scout.LeftHookReady = True
                    w.tick(0.13)
                else:
                    w.tick()
                    w.tick(1.01)
                self.assert_stopped(w, "no_suitable_anchor")
                self.assertEqual(w.controller._attempts, int(second))

    def test_timeout_and_lost_hook(self):
        for failure in ("attachment_timeout", "hook_lost", "hook_not_ready", "sequence_timeout"):
            with self.subTest(failure=failure):
                w = World()
                w.launch()
                if failure == "attachment_timeout":
                    w.tick(3.01)
                elif failure == "sequence_timeout":
                    w.tick(12)
                else:
                    w.attach()
                    if failure == "hook_lost":
                        w.scout.IsHookedLeft = False
                        w.tick()
                    else:
                        w.tick(0.61)
                        w.tick(1.01)
                self.assert_stopped(w, failure)

    def test_death_missing_and_gas_during_active_states(self):
        for state in ("Settle", "Attach", "Burst", "Coast", "Observe"):
            for failure in ("scout_dead", "scout_missing", "insufficient_odm_resources"):
                if state == "Observe" and failure == "insufficient_odm_resources":
                    continue  # Already released; observation needs no gas.
                with self.subTest(state=state, failure=failure):
                    w = World()
                    w.tick()
                    w.controller.Enter(state)
                    w.scout.gas = True
                    if failure == "scout_dead":
                        w.scout.IsAlive = False
                    elif failure == "scout_missing":
                        w.controller._scout = None
                        w.scout.gas = False  # Despawned entity cannot receive calls.
                    else:
                        w.scout.CurrentGas = 0
                    w.tick()
                    self.assertEqual(w.controller._state, "Done")
                    self.assertFalse(w.scout.gas)
                    self.assertTrue(any("result=" + failure in m for m in w.messages))

    def test_collision_guard_cleans_up(self):
        w = World()
        w.launch()
        w.attach()
        w.scout.Velocity = Vector(0, -10, 20)
        w.hit = NS(Point=Vector(4, 1, 3), Distance=3)
        w.tick(0.11)
        self.assert_stopped(w, "collision_risk")

    def test_repeated_start_and_existing_tag(self):
        w = World()
        w.launch()
        w.attach()
        w.controller.OnGameStart()
        self.assert_stopped(w, "repeated_start")
        self.assertEqual(w.spawns, 1)
        w = World()
        w.humans.append(NS(IsAlive=True, Name="AICadetsM1"))
        w.tick()
        self.assertEqual(w.spawns, 0)
        self.assertTrue(any("existing_scout" in m for m in w.messages))

    def test_nonmaster_and_promotion_do_not_spawn(self):
        w = World()
        w.network.IsMasterClient = False
        w.controller._started = False
        w.controller.OnGameStart()
        w.tick()
        w.network.IsMasterClient = True
        w.tick()
        self.assertEqual(w.spawns, 0)

    def test_authority_loss_has_no_illegal_mutations(self):
        for master in (True, False):
            w = World()
            w.launch()
            w.attach()
            before = list(w.scout.calls)
            if master:
                w.network.IsMasterClient = False
            else:
                w.scout.IsMine = False
            w.tick()
            self.assertEqual(w.controller._state, "Done")
            self.assertEqual(before, w.scout.calls)
            self.assertIn("cleanup_unavailable", w.messages[-1])

    def test_host_timeout_invalid_settings_and_spawn_failure(self):
        w = World()
        w.host.Character = None
        w.tick(30.01)
        self.assertEqual(w.controller._state, "Done")
        self.assertEqual(w.spawns, 0)
        for setting, value in (("GasBurstSeconds", 100), ("HookReach", 1000), ("MinimumGas", 0)):
            w = World()
            setattr(w.controller, setting, value)
            w.tick()
            self.assertEqual(w.controller._state, "Done")
            self.assertEqual(w.spawns, 0)
        w = World()
        w.scout = None
        w.tick()
        w.tick(1)
        self.assertEqual(w.spawns, 1)
        self.assertEqual(w.controller._state, "Done")

    def test_nearest_layer_and_candidate_rejections(self):
        w = World()
        w.tick()
        far = NS(Point=Vector(4, 15, 60), Distance=61)
        near = NS(Point=Vector(4, 8, 20), Distance=21)
        w.hit = lambda a, b, layer: far if layer == "map" else near
        self.assertIs(w.controller.MapHit(Vector(0, 0, 0), Vector(0, 0, 70)), near)
        for point, previous in ((Vector(4, 10, 5), None), (Vector(4, 15, 90), None),
                                (Vector(4, 1, 30), None), (Vector(4, 15, -30), None),
                                (Vector(4, 15, 40), Vector(4, 15, 39))):
            w.controller._anchor = None
            w.controller._previousAnchor = previous
            w.hit = NS(Point=point, Distance=40)
            w.controller.ConsiderAnchor(Vector(0, 0, 1), 12)
            self.assertIsNone(w.controller._anchor)

    def test_spawn_corridor_and_early_release(self):
        w = World()
        w.hit = NS(Point=Vector(2, 1, 0), Distance=2)
        w.tick()
        self.assertEqual(w.spawns, 0)
        self.assertTrue(any("spawn_path_blocked" in m for m in w.messages))
        w = World()
        w.launch()
        w.attach()
        w.scout.Position = w.controller._anchor - Vector(0, 0, 9)
        w.tick()
        self.assertEqual(w.controller._state, "Coast")
        self.assertFalse(w.scout.gas)

    def test_command_error_does_not_retry_launch(self):
        w = World()
        w.tick()
        w.hit = NS(Point=Vector(4, 15, 45), Distance=46)

        def broken_launch(point):
            raise RuntimeError("synthetic engine error")

        w.scout.LaunchHookLeft = broken_launch
        with self.assertRaises(RuntimeError):
            w.tick(1.01)
        self.assertEqual(w.controller._state, "Attach")
        w.hit = None
        w.tick(3.01)
        self.assert_stopped(w, "attachment_timeout")
        self.assertEqual(w.controller._attempts, 1)


if __name__ == "__main__":
    unittest.main()
