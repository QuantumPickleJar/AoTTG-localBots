# M1 experiment. Enable alone in a private, quiet lobby; see docs/M1_TESTING.md.
# Uses ordinary hook/gas inputs. Never writes position, velocity or resources.
addon AICadetsTraversal
{
    Description = "M1: one Scout, two sequential left-hook maneuvers, bounded cleanup.";
    SpawnSide = 4.0;
    HookReach = 70.0;
    AnchorRise = 12.0;
    GasBurstSeconds = 0.6;
    GasBurstSecondsTooltip = "Maximum burst per anchor (0.1 to 0.8 seconds).";
    MinimumGas = 2.0;
    MinimumGasTooltip = "Abort at this reserve; no gas is refilled by this add-on.";

    _started = false;
    _eligible = false;
    _scout = null;
    _state = "Dormant";
    _stateStart = 0.0;
    _runStart = 0.0;
    _leg = 0;
    _attempts = 0;
    _attachments = 0;
    _initialPosition = null;
    _initialGas = 0.0;
    _lastPosition = null;
    _lastGas = 0.0;
    _direction = null;
    _anchor = null;
    _previousAnchor = null;
    _bestScore = -100000.0;
    _nextRiskCheck = 0.0;

    function OnGameStart()
    {
        # Do not forget a live Scout on a repeated callback. A new instance also
        # checks Game.AIHumans before spawning. No automatic migration/resume.
        if (self._started)
        {
            self.Finish("repeated_start");
            return;
        }
        self._started = true;
        self._eligible = Network.IsMasterClient;
        if (!self._eligible)
        {
            return;
        }
        self._runStart = Time.GameTime;
        self.Enter("WaitHost");
        Game.Print("[AI Cadets M1] Ready: face along a clear route with staggered walls/trees. Host spawn timeout: 30s.");
    }

    function OnTick()
    {
        if (!self._eligible || self._state == "Done" || self._state == "Dormant")
        {
            return;
        }
        if (!Network.IsMasterClient)
        {
            # Cannot legally mutate the Scout after losing master authority.
            self.Finish("master_lost_cleanup_unavailable");
            return;
        }
        if (self._state == "WaitHost")
        {
            if (Time.GameTime - self._stateStart >= 30.0)
            {
                self.Finish("host_timeout");
                return;
            }
            host = Network.MyPlayer.Character;
            if (host == null || host.Type != "Human" || !host.IsAlive)
            {
                return;
            }
            self.SpawnScout(host);
            return;
        }
        if (self._scout == null)
        {
            self.Finish("scout_missing");
            return;
        }
        if (!self._scout.IsMine)
        {
            self.Finish("ownership_lost_cleanup_unavailable");
            return;
        }
        if (!self._scout.IsAlive)
        {
            self.Finish("scout_dead");
            return;
        }
        self._lastPosition = self._scout.Position;
        self._lastGas = self._scout.CurrentGas;
        if (Time.GameTime - self._runStart >= 12.0)
        {
            self.Finish("sequence_timeout");
            return;
        }
        if (self._state == "Observe")
        {
            if (Time.GameTime - self._stateStart >= 1.0)
            {
                self.Finish("completed");
            }
            return;
        }
        if (self._scout.CurrentGas <= self.MinimumGas || !self._scout.LeftHookEnabled)
        {
            self.Finish("insufficient_odm_resources");
            return;
        }
        # 10 Hz guard using actual velocity; no simulated forces or braking.
        if (Time.GameTime >= self._nextRiskCheck)
        {
            self._nextRiskCheck = Time.GameTime + 0.1;
            if (self.CollisionRisk())
            {
                self.Finish("collision_risk");
                return;
            }
        }
        if (self._state == "Settle")
        {
            if (Time.GameTime - self._stateStart >= 1.0)
            {
                self.BeginLeg();
            }
            return;
        }
        if (self._state == "Attach")
        {
            if (Time.GameTime - self._stateStart >= 3.0)
            {
                self.Finish("attachment_timeout");
                return;
            }
            if (self._scout.IsHookedLeft)
            {
                self._attachments = self._attachments + 1;
                self.Enter("Burst");
                self._scout.UseGas(true);
                self.LogSnapshot("attached");
            }
            return;
        }
        if (self._state == "Burst")
        {
            if (!self._scout.IsHookedLeft)
            {
                self.Finish("hook_lost");
                return;
            }
            # Release before reaching the surface, or at the bounded burst cap.
            if (Vector3.Distance(self._scout.Position, self._anchor) <= 10.0 || Time.GameTime - self._stateStart >= self.GasBurstSeconds)
            {
                self.StopODM();
                self.LogSnapshot("released");
                if (self._leg == 1)
                {
                    self.Enter("Coast");
                }
                else
                {
                    self.Enter("Observe");
                }
            }
            return;
        }
        if (self._state == "Coast")
        {
            if (Time.GameTime - self._stateStart >= 1.0)
            {
                self.Finish("hook_not_ready");
                return;
            }
            if (Time.GameTime - self._stateStart >= 0.12 && self._scout.LeftHookReady && !self._scout.IsHookedLeft)
            {
                self.BeginLeg();
            }
            return;
        }
        self.Finish("invalid_state");
    }

    function SpawnScout(host)
    {
        if (self.HookReach < 20.0 || self.HookReach > 70.0 || self.AnchorRise < 4.0 || self.AnchorRise > 25.0 || self.GasBurstSeconds < 0.1 || self.GasBurstSeconds > 0.8 || self.MinimumGas < 1.0 || self.SpawnSide < 2.0 || self.SpawnSide > 6.0)
        {
            self.Finish("invalid_settings");
            return;
        }
        for (human in Game.AIHumans)
        {
            if (human.IsAlive && human.Name == "AICadetsM1")
            {
                self.Finish("existing_scout_restart_lobby");
                return;
            }
        }
        # Check the short spawn-offset corridor, not a full capsule overlap.
        spawnPos = host.Position + host.Right * self.SpawnSide;
        if (self.MapHit(host.Position + Vector3(0.0, 1.0, 0.0), spawnPos + Vector3(0.0, 1.0, 0.0)) != null)
        {
            self.Finish("spawn_path_blocked");
            return;
        }
        self._direction = Vector3.Normalize(Vector3(host.Forward.X, 0.0, host.Forward.Z));
        # Latch before invoking spawn: a runtime failure must not retry each tick.
        self.Enter("Done");
        self._scout = Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades, spawnPos, 0.0);
        if (self._scout == null || !self._scout.IsMine || !self._scout.IsAlive)
        {
            self.StopODM();
            Game.Print("[AI Cadets M1] result=spawn_failed_or_not_owned attempts=0 attachments=0 displacement=n/a gas_used=n/a");
            return;
        }
        self._scout.Name = "AICadetsM1";
        self._scout.SetDisplayName("AICadetsM1", true);
        self._scout.Idle();
        self._initialPosition = self._scout.Position;
        self._initialGas = self._scout.CurrentGas;
        self._lastPosition = self._initialPosition;
        self._lastGas = self._initialGas;
        self._runStart = Time.GameTime;
        self.Enter("Settle");
    }

    function BeginLeg()
    {
        if (!self._scout.LeftHookReady)
        {
            self.Finish("hook_not_ready");
            return;
        }
        self._leg = self._leg + 1;
        self._previousAnchor = self._anchor;
        velocity = self._scout.Velocity;
        horizontal = Vector3(velocity.X, 0.0, velocity.Z);
        if (self._leg == 2 && horizontal.Magnitude >= 2.0)
        {
            self._direction = horizontal.Normalized;
        }
        self._anchor = null;
        self._bestScore = -100000.0;
        right = Vector3(self._direction.Z, 0.0, 0.0 - self._direction.X);
        self.ConsiderAnchor(self._direction, self.AnchorRise);
        self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 0.45), self.AnchorRise);
        self.ConsiderAnchor(Vector3.Normalize(self._direction - right * 0.45), self.AnchorRise);
        self.ConsiderAnchor(self._direction, self.AnchorRise * 2.0);
        self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 0.8), self.AnchorRise);
        if (self._anchor == null)
        {
            self.Finish("no_suitable_anchor");
            return;
        }
        # Latch the attachment deadline before issuing commands, so an engine
        # error cannot cause repeated launch attempts from Settle/Coast.
        self.Enter("Attach");
        self._scout.AimAt(self._anchor);
        if (self._leg == 1)
        {
            self._scout.Jump();
        }
        self._attempts = self._attempts + 1;
        self._scout.LaunchHookLeft(self._anchor);
        self.LogSnapshot("launched anchor=" + Convert.ToString(self._anchor));
    }

    function ConsiderAnchor(direction, rise)
    {
        start = self._scout.Position + Vector3(0.0, 3.0, 0.0);
        ray = Vector3.Normalize(direction * self.HookReach + Vector3(0.0, rise, 0.0));
        hit = self.MapHit(start, start + ray * self.HookReach);
        if (hit == null)
        {
            return;
        }
        delta = hit.Point - self._scout.Position;
        distance = delta.Magnitude;
        if (distance < 15.0 || distance > self.HookReach || delta.Y < 4.0)
        {
            return;
        }
        if (self._previousAnchor != null && Vector3.Distance(hit.Point, self._previousAnchor) < 12.0)
        {
            return;
        }
        horizontal = Vector3(delta.X, 0.0, delta.Z);
        alignment = Vector3.Dot(horizontal.Normalized, self._direction);
        if (alignment < 0.35)
        {
            return;
        }
        # Prefer continuing forward and some runway over pulling into a near wall.
        score = alignment * 50.0 + distance * 0.25;
        if (score > self._bestScore)
        {
            self._anchor = hit.Point;
            self._bestScore = score;
        }
    }

    function MapHit(start, end)
    {
        # Compare both layers: a farther MapObjects hit must not hide a nearer
        # MapEditor obstruction. Attachment itself still determines hookability.
        hit = Physics.LineCast(start, end, CollideWithEnum.MapObjects);
        editorHit = Physics.LineCast(start, end, CollideWithEnum.MapEditor);
        if (hit == null)
        {
            return editorHit;
        }
        if (editorHit != null && editorHit.Distance < hit.Distance)
        {
            return editorHit;
        }
        return hit;
    }

    function CollisionRisk()
    {
        velocity = self._scout.Velocity;
        if (velocity.Magnitude < 2.0)
        {
            return false;
        }
        start = self._scout.Position + Vector3(0.0, 1.0, 0.0);
        end = start + velocity * 0.2 + velocity.Normalized * 2.0;
        return self.MapHit(start, end) != null;
    }

    function Enter(state)
    {
        self._state = state;
        self._stateStart = Time.GameTime;
    }

    function StopODM()
    {
        if (Network.IsMasterClient && self._scout != null && self._scout.IsMine)
        {
            self._scout.UseGas(false);
            self._scout.ReleaseHookLeft();
            self._scout.ReleaseHookRight();
        }
    }

    function LogSnapshot(event)
    {
        Game.Print("[AI Cadets M1] leg=" + Convert.ToString(self._leg) + " event=" + event + " position=" + Convert.ToString(self._scout.Position) + " velocity=" + Convert.ToString(self._scout.Velocity) + " gas=" + Convert.ToString(self._scout.CurrentGas));
    }

    function Finish(reason)
    {
        self.StopODM();
        if (self._state == "Done")
        {
            return;
        }
        displacement = "n/a";
        gasUsed = "n/a";
        if (self._initialPosition != null && self._lastPosition != null)
        {
            displacement = Convert.ToString(Vector3.Distance(self._lastPosition, self._initialPosition));
            gasUsed = Convert.ToString(self._initialGas - self._lastGas);
        }
        Game.Print("[AI Cadets M1] result=" + reason + " state=" + self._state + " leg=" + Convert.ToString(self._leg) + " attempts=" + Convert.ToString(self._attempts) + " attachments=" + Convert.ToString(self._attachments) + " displacement=" + displacement + " gas_used=" + gasUsed + " (last live sample)");
        self.Enter("Done");
    }
}
