# AI Cadets: first local ODM probe for AoTTG2 Custom Logic.
# Select this addon in a PRIVATE game. Face a nearby, hookable wall or tree.
# This is a proposed API-level prototype and requires in-game validation.

addon AICadetsProbe
{
    Description = "Spawn one AI Scout and test one ODM hook, gas burst, and release.";

    SpawnSide = 4.0;
    SpawnSideTooltip = "Scout spawn offset to the right of the local host (world units).";
    HookReach = 70.0;
    HookReachTooltip = "Maximum distance probed ahead of the host for a hookable surface.";
    AnchorRise = 12.0;
    AnchorRiseTooltip = "How high the target probe rises above its starting point.";
    GasBurstSeconds = 0.6;
    GasBurstSecondsTooltip = "Gas duration after the hook attaches.";

    _scout = null;
    _phase = 0;
    _phaseStart = 0.0;
    _aimDirection = null;
    _initialPosition = null;
    _initialGas = 0.0;

    function OnGameStart()
    {
        self._scout = null;
        self._phase = 0;
        self._phaseStart = Time.GameTime;
        self._aimDirection = null;
        self._initialPosition = null;
        self._initialGas = 0.0;
        if (Network.IsMasterClient)
        {
            Game.Print("[AI Cadets] Face a nearby wall/tree. Probe starts once the host spawns.");
        }
    }

    function OnSecond()
    {
        if (!Network.IsMasterClient)
        {
            return;
        }

        if (self._phase == 0)
        {
            host = Network.MyPlayer.Character;
            if (host == null || host.Type != "Human" || !host.IsAlive)
            {
                return;
            }

            # Use the player's known safe spawn area and sight line as test geometry.
            self._aimDirection = host.Forward;
            spawnPos = host.Position + host.Right * self.SpawnSide;
            self._scout = Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades, spawnPos, 0.0);
            if (self._scout == null)
            {
                Game.Print("[AI Cadets] SpawnHumanAt returned null. Check the console and host ownership.");
                self._phase = 5;
                return;
            }

            self._scout.SetDisplayName("[BOT] Scout 01", true);
            self._scout.Idle();
            self._phase = 1;
            self._phaseStart = Time.GameTime;
            Game.Print("[AI Cadets] Scout spawned. Looking for a hookable surface...");
            return;
        }

        if (self._phase == 1 && Time.GameTime - self._phaseStart >= 1.0)
        {
            if (self._scout == null || !self._scout.IsAlive)
            {
                Game.Print("[AI Cadets] Scout is not alive before ODM test.");
                self._phase = 5;
                return;
            }

            start = self._scout.Position + Vector3(0.0, 3.0, 0.0);
            end = start + self._aimDirection * self.HookReach + Vector3(0.0, self.AnchorRise, 0.0);
            hit = Physics.LineCast(start, end, CollideWithEnum.MapObjects);
            if (hit == null)
            {
                hit = Physics.LineCast(start, end, CollideWithEnum.MapEditor);
            }
            if (hit == null)
            {
                Game.Print("[AI Cadets] No surface hit. Reposition to face a wall, then restart the round.");
                self._phase = 5;
                return;
            }

            self._initialPosition = self._scout.Position;
            self._initialGas = self._scout.CurrentGas;
            self._scout.AimAt(hit.Point);
            self._scout.Jump();
            self._scout.LaunchHookLeft(hit.Point);
            self._phase = 2;
            self._phaseStart = Time.GameTime;
            Game.Print("[AI Cadets] Hook launched; waiting for attachment...");
            return;
        }

        if (self._phase == 4 && Time.GameTime - self._phaseStart >= 1.0)
        {
            displacement = Vector3.Distance(self._scout.Position, self._initialPosition);
            gasUsed = self._initialGas - self._scout.CurrentGas;
            Game.Print("[AI Cadets] Probe finished. Displacement: " + Convert.ToString(displacement) + ", gas used: " + Convert.ToString(gasUsed));
            self._phase = 5;
        }
    }

    function OnTick()
    {
        if (!Network.IsMasterClient || self._scout == null)
        {
            return;
        }
        if (self._phase != 2 && self._phase != 3)
        {
            return;
        }
        if (!self._scout.IsAlive)
        {
            self.StopODM();
            Game.Print("[AI Cadets] Scout died during probe.");
            self._phase = 5;
            return;
        }

        if (self._phase == 2)
        {
            if (self._scout.IsHookedLeft)
            {
                self._scout.UseGas(true);
                self._phase = 3;
                self._phaseStart = Time.GameTime;
                Game.Print("[AI Cadets] Hook attached; short gas burst started.");
            }
            elif (Time.GameTime - self._phaseStart > 3.0)
            {
                self.StopODM();
                self._phase = 5;
                Game.Print("[AI Cadets] Hook attachment timeout; check target and collision layers.");
            }
            return;
        }

        if (self._phase == 3 && Time.GameTime - self._phaseStart >= self.GasBurstSeconds)
        {
            self.StopODM();
            self._phase = 4;
            self._phaseStart = Time.GameTime;
            Game.Print("[AI Cadets] Gas off; left hook released.");
        }
    }

    function StopODM()
    {
        if (self._scout != null)
        {
            self._scout.UseGas(false);
            self._scout.ReleaseHookLeft();
        }
    }
}
