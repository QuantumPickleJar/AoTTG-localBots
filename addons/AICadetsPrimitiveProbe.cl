# Isolated, opt-in M3 primitive probe. Private local host only.
# Commands are documented as of 2026-10-31; no primitive mechanics are validated here.
addon AICadetsPrimitiveProbe
{
    Description = "Opt-in one-cadet movement primitive probe. Private host only; one case per run.";
    RunTest = false;
    RunTestTooltip = "Leave false unless running a private, isolated primitive validation session.";
    TestCase = "Dodge";
    TestCaseTooltip = "Dodge, Jump, DashForward, DashBackward, DashLeft, DashRight, GasPulse, JumpDashForward, AirDashForward, GroundMove, HookLeft.";
    ActionSeconds = 0.6;
    ObserveSeconds = 1.5;

    _scout = null;
    _phase = 0;
    _phaseStart = 0.0;
    _actionEnd = 0.0;
    _observeEnd = 0.0;
    _airSince = 0.0;
    _positionBefore = null;
    _velocityBefore = null;
    _gasBefore = 0.0;
    _moveDuration = 0.6;
    _observeDuration = 1.5;
    _direction = null;
    _right = null;
    _gasActive = false;
    _hookActive = false;

    function OnGameStart()
    {
        self._scout = null;
        self._phase = 0;
        self._phaseStart = Time.GameTime;
        self._actionEnd = 0.0;
        self._observeEnd = 0.0;
        self._airSince = 0.0;
        self._positionBefore = null;
        self._velocityBefore = null;
        self._gasBefore = 0.0;
        self._moveDuration = self.ActionSeconds;
        if (self._moveDuration < 0.1)
        {
            self._moveDuration = 0.1;
        }
        if (self._moveDuration > 1.0)
        {
            self._moveDuration = 1.0;
        }
        self._observeDuration = self.ObserveSeconds;
        if (self._observeDuration < 0.1)
        {
            self._observeDuration = 0.1;
        }
        if (self._observeDuration > 3.0)
        {
            self._observeDuration = 3.0;
        }
        self._direction = null;
        self._right = null;
        self._gasActive = false;
        self._hookActive = false;
        if (!self.RunTest)
        {
            return;
        }
        if (!Network.IsMasterClient)
        {
            Game.Print("[AI Cadets Primitive] Run only from the private lobby master host.");
            self._phase = 6;
            return;
        }
        Game.Print("[AI Cadets Primitive] Opt-in test armed. Exactly one test case will run; no physics or health values are written.");
    }

    function OnSecond()
    {
        if (!self.RunTest || self._phase != 0 || !Network.IsMasterClient)
        {
            return;
        }
        host = Network.MyPlayer.Character;
        if (host == null || host.Type != "Human" || !host.IsAlive)
        {
            return;
        }
        self._direction = host.Forward;
        self._right = host.Right;
        spawnPos = host.Position + host.Right * 4.0;
        self._scout = Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades, spawnPos, 0.0);
        if (self._scout == null)
        {
            Game.Print("[AI Cadets Primitive] SpawnHumanAt returned null; test stopped.");
            self._phase = 6;
            return;
        }
        self._scout.SetDisplayName("[PROBE] M3 Primitive", true);
        PersistentData.SetProperty("AICadetsPrimitiveViewID", self._scout.ViewID);
        self._phase = 1;
        self._phaseStart = Time.GameTime;
        Game.Print("[AI Cadets Primitive] One probe spawned. Waiting up to 10 seconds for grounded start state.");
    }

    function OnTick()
    {
        if (!self.RunTest || self._phase == 0 || self._phase == 6)
        {
            return;
        }
        if (!Network.IsMasterClient)
        {
            self.StopInputs();
            Game.Print("[AI Cadets Primitive] Master ownership changed; test stopped.");
            self._phase = 6;
            return;
        }
        if (self._scout == null || !self._scout.IsAlive)
        {
            Game.Print("[AI Cadets Primitive] Probe missing or dead; no success inferred.");
            self._phase = 6;
            return;
        }
        if (self._phase == 1)
        {
            if (self._scout.Grounded)
            {
                self.BeginSelectedCase();
                return;
            }
            if (Time.GameTime - self._phaseStart >= 10.0)
            {
                self.Finish("abort_not_grounded");
            }
            return;
        }
        if (self._phase == 2)
        {
            if (!self._scout.Grounded)
            {
                if (self._airSince == 0.0)
                {
                    self._airSince = Time.GameTime;
                }
                if (self.TestCase == "JumpDashForward" || Time.GameTime - self._airSince >= 0.25)
                {
                    self.CaptureBefore();
                    self._scout.Dash(self._direction);
                    self._phase = 4;
                    self._actionEnd = Time.GameTime + 1.0;
                    Game.Print("[AI Cadets Primitive] Dash command issued in observed airborne state.");
                }
            }
            elif (Time.GameTime - self._phaseStart >= 1.5)
            {
                self.Finish("abort_takeoff_not_observed");
            }
            return;
        }
        if (self._phase == 3)
        {
            if (self._scout.IsHookedLeft)
            {
                self.CaptureBefore();
                self._scout.UseGas(true);
                self._gasActive = true;
                self._hookActive = true;
                self._phase = 4;
                self._actionEnd = Time.GameTime + 0.35;
                Game.Print("[AI Cadets Primitive] Left-hook attachment observed; short gas pulse started.");
            }
            elif (Time.GameTime - self._phaseStart >= 3.0)
            {
                self.Finish("abort_hook_attach_not_observed");
            }
            return;
        }
        if (self._phase == 4)
        {
            if (self.TestCase == "GroundMove" && Time.GameTime < self._actionEnd)
            {
                self._scout.Move(self._direction);
            }
            if (Time.GameTime >= self._actionEnd)
            {
                self.StopInputs();
                self._phase = 5;
                self._observeEnd = Time.GameTime + self._observeDuration;
                Game.Print("[AI Cadets Primitive] Action window ended; passive observation continues.");
            }
            return;
        }
        if (self._phase == 5 && Time.GameTime >= self._observeEnd)
        {
            self.Finish("observation_complete");
        }
    }

    function BeginSelectedCase()
    {
        if (self.TestCase == "JumpDashForward" || self.TestCase == "AirDashForward")
        {
            self._airSince = 0.0;
            self._scout.Jump();
            self._phase = 2;
            self._phaseStart = Time.GameTime;
            Game.Print("[AI Cadets Primitive] Jump command issued; waiting for observed airborne state before Dash.");
            return;
        }
        if (self.TestCase == "HookLeft")
        {
            start = self._scout.Position + Vector3(0.0, 3.0, 0.0);
            end = start + self._direction * 70.0 + Vector3(0.0, 12.0, 0.0);
            hit = Physics.LineCast(start, end, CollideWithEnum.MapObjects);
            if (hit == null)
            {
                hit = Physics.LineCast(start, end, CollideWithEnum.MapEditor);
            }
            if (hit == null)
            {
                self.Finish("abort_no_hook_surface");
                return;
            }
            self.CaptureBefore();
            self._scout.AimAt(hit.Point);
            self._scout.Jump();
            self._scout.LaunchHookLeft(hit.Point);
            self._phase = 3;
            self._phaseStart = Time.GameTime;
            Game.Print("[AI Cadets Primitive] Single left-hook command issued; attachment must be observed.");
            return;
        }
        self.CaptureBefore();
        if (self.TestCase == "Dodge")
        {
            if (!self._scout.CanDodge)
            {
                self.Finish("skip_dodge_unavailable");
                return;
            }
            self._scout.Dodge();
            self.StartObserveWindow("Dodge");
            return;
        }
        if (self.TestCase == "Jump")
        {
            self._scout.Jump();
            self.StartObserveWindow("Jump");
            return;
        }
        if (self.TestCase == "DashForward")
        {
            self._scout.Dash(self._direction);
            self.StartObserveWindow("DashForward");
            return;
        }
        if (self.TestCase == "DashBackward")
        {
            self._scout.Dash(self._direction * -1.0);
            self.StartObserveWindow("DashBackward");
            return;
        }
        if (self.TestCase == "DashLeft")
        {
            self._scout.Dash(self._right * -1.0);
            self.StartObserveWindow("DashLeft");
            return;
        }
        if (self.TestCase == "DashRight")
        {
            self._scout.Dash(self._right);
            self.StartObserveWindow("DashRight");
            return;
        }
        if (self.TestCase == "GasPulse")
        {
            if (self._scout.CurrentGas <= 0.0)
            {
                self.Finish("skip_no_gas");
                return;
            }
            self._scout.UseGas(true);
            self._gasActive = true;
            self._phase = 4;
            self._actionEnd = Time.GameTime + 0.25;
            Game.Print("[AI Cadets Primitive] Grounded UseGas pulse started for 0.25 seconds.");
            return;
        }
        if (self.TestCase == "GroundMove")
        {
            self._phase = 4;
            self._actionEnd = Time.GameTime + self._moveDuration;
            self._scout.Move(self._direction);
            Game.Print("[AI Cadets Primitive] Ground Move command started in clear test geometry.");
            return;
        }
        self.Finish("abort_unknown_test_case");
    }

    function CaptureBefore()
    {
        self._positionBefore = self._scout.Position;
        self._velocityBefore = self._scout.Velocity;
        self._gasBefore = self._scout.CurrentGas;
    }

    function StartObserveWindow(label)
    {
        self._phase = 4;
        self._actionEnd = Time.GameTime + 1.0;
        Game.Print("[AI Cadets Primitive] " + label + " command issued once; observing physical response.");
    }

    function StopInputs()
    {
        if (self._scout != null && self._scout.IsAlive)
        {
            self._scout.UseGas(false);
            self._scout.Move(Vector3(0.0, 0.0, 0.0));
            if (self._hookActive || self._scout.IsHookedLeft || self._scout.IsHookingLeft)
            {
                self._scout.ReleaseHookLeft();
            }
        }
        self._gasActive = false;
        self._hookActive = false;
    }

    function Finish(result)
    {
        self.StopInputs();
        if (self._positionBefore != null && self._scout != null && self._scout.IsAlive)
        {
            displacement = Vector3.Distance(self._positionBefore, self._scout.Position);
            velocityChange = Vector3.Distance(self._velocityBefore, self._scout.Velocity);
            gasDelta = self._gasBefore - self._scout.CurrentGas;
            Game.Print("[AI Cadets Primitive] Result=" + result + " case=" + self.TestCase + " displacement=" + Convert.ToString(displacement) + " delta_v=" + Convert.ToString(velocityChange) + " gas_delta=" + Convert.ToString(gasDelta) + " state=" + self._scout.State + " grounded=" + Convert.ToString(self._scout.Grounded));
        }
        else
        {
            Game.Print("[AI Cadets Primitive] Result=" + result + " case=" + self.TestCase + "; no physical success inferred.");
        }
        self._phase = 6;
    }
}
