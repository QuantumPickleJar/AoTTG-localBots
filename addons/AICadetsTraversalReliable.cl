# M1 reliability candidate. Keep AICadetsTraversal.cl and AICadetsWatcher.cl as
# v3 baselines during A/B gameplay verification.
addon AICadetsTraversalReliable
{
    Description = "M1 reliability candidate: two-anchor traversal with bounded recovery and diagnostic events.";
    SpawnSide = 4.0;
    HookReach = 70.0;
    AnchorRise = 12.0;
    GasBurstSeconds = 0.6;
    GasBurstSecondsTooltip = "Maximum burst per traversal anchor (0.1 to 0.8 seconds).";
    RecoveryBurstSeconds = 0.35;
    RecoveryBurstSecondsTooltip = "Emergency burst cap after recovery hook attach (0.1 to 0.6 seconds).";
    MinimumGas = 2.0;
    MinimumGasTooltip = "Stop traversal at this reserve. No refill is performed.";
    RecoveryGasReserve = 6.0;
    RecoveryGasReserveTooltip = "Minimum gas required before attempting an emergency recovery hook.";
    ObserveSeconds = 2.0;
    ObserveSecondsTooltip = "Post-release observation window before final success.";
    RecoveryAttachTimeout = 1.8;
    RecoveryAttachTimeoutTooltip = "Maximum wait for a recovery hook attachment.";
    MaxRecoveryAttempts = 1;
    MaxRecoveryAttemptsTooltip = "Maximum emergency recoveries per run.";
    Diagnostics = true;
    DiagnosticsTooltip = "Emit bounded machine-readable decision events.";

    _started = false;
    _eligible = false;
    _scout = null;
    _state = "Dormant";
    _stateStart = 0.0;
    _runStart = 0.0;
    _leg = 0;
    _attempts = 0;
    _attachments = 0;
    _recoveries = 0;
    _initialPosition = null;
    _initialGas = 0.0;
    _lastPosition = null;
    _lastGas = 0.0;
    _direction = null;
    _anchor = null;
    _previousAnchor = null;
    _bestScore = -100000.0;
    _nextRiskCheck = 0.0;
    _lastResultClass = "none";
    _lastResultReason = "none";
    _logCount = 0;
    _legRejectLogs = 0;
    _coastSpeedLowAt = -1.0;
    _recovering = false;
    _anchorMode = "primary";

    function OnGameStart()
    {
        if (self._started)
        {
            self.Terminate("safe_termination", "repeated_start");
            return;
        }
        self._started = true;
        self._eligible = Network.IsMasterClient;
        if (!self._eligible)
        {
            return;
        }
        self._runStart = Time.GameTime;
        self.Enter("WaitHost", "startup");
        self.Emit("ready", "host_timeout=30");
    }

    function OnTick()
    {
        if (!self._eligible || self._state == "Done" || self._state == "Dormant")
        {
            return;
        }
        if (!Network.IsMasterClient)
        {
            self.Terminate("safe_termination", "master_lost_cleanup_unavailable");
            return;
        }
        if (self._state == "WaitHost")
        {
            if (Time.GameTime - self._stateStart >= 30.0)
            {
                self.Terminate("failure", "host_timeout");
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
            self.Terminate("safe_termination", "scout_missing");
            return;
        }
        if (!self._scout.IsMine)
        {
            self.Terminate("safe_termination", "ownership_lost_cleanup_unavailable");
            return;
        }
        if (!self._scout.IsAlive)
        {
            self.Terminate("safe_termination", "scout_dead");
            return;
        }

        self._lastPosition = self._scout.Position;
        self._lastGas = self._scout.CurrentGas;
        if (Time.GameTime - self._runStart >= 14.0)
        {
            self.Terminate("failure", "sequence_timeout");
            return;
        }
        if (self._state == "Observe")
        {
            self.ObserveStep();
            return;
        }
        if (self._scout.CurrentGas <= self.MinimumGas || !self._scout.LeftHookEnabled)
        {
            self.Terminate("safe_termination", "insufficient_odm_resources");
            return;
        }
        if (Time.GameTime >= self._nextRiskCheck)
        {
            self._nextRiskCheck = Time.GameTime + 0.1;
            if (self.CollisionRisk())
            {
                self.Terminate("safe_termination", "collision_risk");
                return;
            }
        }

        if (self._state == "Settle")
        {
            if (Time.GameTime - self._stateStart >= 1.0)
            {
                self.BeginTraversalLeg();
            }
            return;
        }
        if (self._state == "Attach")
        {
            self.AttachStep(3.0, false);
            return;
        }
        if (self._state == "Burst")
        {
            self.BurstStep(self.GasBurstSeconds, false);
            return;
        }
        if (self._state == "Coast")
        {
            self.CoastStep();
            return;
        }
        if (self._state == "RecoverPlan")
        {
            self.BeginRecoveryLeg();
            return;
        }
        if (self._state == "RecoverAttach")
        {
            self.AttachStep(self.RecoveryAttachTimeout, true);
            return;
        }
        if (self._state == "RecoverBurst")
        {
            self.BurstStep(self.RecoveryBurstSeconds, true);
            return;
        }
        self.Terminate("failure", "invalid_state");
    }

    function SpawnScout(host)
    {
        if (self.HookReach < 20.0 || self.HookReach > 70.0 || self.AnchorRise < 4.0 || self.AnchorRise > 25.0 || self.GasBurstSeconds < 0.1 || self.GasBurstSeconds > 0.8 || self.RecoveryBurstSeconds < 0.1 || self.RecoveryBurstSeconds > 0.6 || self.MinimumGas < 1.0 || self.RecoveryGasReserve <= self.MinimumGas || self.ObserveSeconds < 1.0 || self.ObserveSeconds > 3.0 || self.RecoveryAttachTimeout < 0.8 || self.RecoveryAttachTimeout > 3.0 || self.SpawnSide < 2.0 || self.SpawnSide > 6.0 || self.MaxRecoveryAttempts < 0 || self.MaxRecoveryAttempts > 2)
        {
            self.Terminate("failure", "invalid_settings");
            return;
        }
        for (human in Game.AIHumans)
        {
            if (human.IsAlive && (human.Name == "AICadetsM1" || human.Name == "AICadetsM1R"))
            {
                self.Terminate("safe_termination", "existing_scout_restart_lobby");
                return;
            }
        }
        spawnPos = host.Position + host.Right * self.SpawnSide;
        if (self.MapHit(host.Position + Vector3(0.0, 1.0, 0.0), spawnPos + Vector3(0.0, 1.0, 0.0)) != null)
        {
            self.Terminate("safe_termination", "spawn_path_blocked");
            return;
        }
        self._direction = Vector3.Normalize(Vector3(host.Forward.X, 0.0, host.Forward.Z));
        self.Enter("Done", "spawn_latched");
        self._scout = Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades, spawnPos, 0.0);
        if (self._scout == null || !self._scout.IsMine || !self._scout.IsAlive)
        {
            self.StopODM();
            Game.Print("[AI Cadets M1R] result_class=failure result_reason=spawn_failed_or_not_owned attempts=0 attachments=0 recoveries=0 displacement=n/a gas_used=n/a");
            return;
        }
        self._scout.Name = "AICadetsM1";
        self._scout.SetDisplayName("AICadetsM1R", true);
        self._scout.Idle();
        self._initialPosition = self._scout.Position;
        self._initialGas = self._scout.CurrentGas;
        self._lastPosition = self._initialPosition;
        self._lastGas = self._initialGas;
        self._runStart = Time.GameTime;
        self.Enter("Settle", "spawned");
    }

    function BeginTraversalLeg()
    {
        if (!self._scout.LeftHookReady)
        {
            self.Terminate("recoverable_interruption", "hook_not_ready");
            return;
        }
        self._leg = self._leg + 1;
        self._previousAnchor = self._anchor;
        self._recovering = false;
        self._anchorMode = "primary";
        self._legRejectLogs = 0;
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
            if (self._leg == 2)
            {
                self.Enter("RecoverPlan", "second_anchor_missing");
            }
            else
            {
                self.Terminate("failure", "no_suitable_anchor");
            }
            return;
        }
        self.Emit("anchor_selected", "mode=primary anchor=" + Convert.ToString(self._anchor));
        self.LaunchCurrentAnchor("Attach");
    }

    function BeginRecoveryLeg()
    {
        if (self._recoveries >= self.MaxRecoveryAttempts)
        {
            self.Terminate("safe_termination", "recovery_budget_exhausted");
            return;
        }
        if (!self._scout.LeftHookEnabled || !self._scout.LeftHookReady || self._scout.CurrentGas < self.RecoveryGasReserve)
        {
            self.Terminate("safe_termination", "recovery_unavailable_resources");
            return;
        }
        velocity = self._scout.Velocity;
        horizontal = Vector3(velocity.X, 0.0, velocity.Z);
        if (horizontal.Magnitude >= 1.0)
        {
            self._direction = horizontal.Normalized;
        }
        else
        {
            self._direction = Vector3.Normalize(Vector3(self._direction.X, 0.0, self._direction.Z));
        }
        self._recovering = true;
        self._anchorMode = "recovery";
        self._legRejectLogs = 0;
        self._anchor = null;
        self._bestScore = -100000.0;
        right = Vector3(self._direction.Z, 0.0, 0.0 - self._direction.X);
        self.ConsiderAnchor(self._direction, self.AnchorRise * 2.0);
        self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 0.75), self.AnchorRise * 2.0);
        self.ConsiderAnchor(Vector3.Normalize(self._direction - right * 0.75), self.AnchorRise * 2.0);
        self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 1.2), self.AnchorRise * 2.5);
        self.ConsiderAnchor(Vector3.Normalize(self._direction - right * 1.2), self.AnchorRise * 2.5);
        if (self._anchor == null)
        {
            self.Terminate("safe_termination", "recovery_no_anchor");
            return;
        }
        self._recoveries = self._recoveries + 1;
        self.Emit("anchor_selected", "mode=recovery anchor=" + Convert.ToString(self._anchor));
        self.LaunchCurrentAnchor("RecoverAttach");
    }

    function LaunchCurrentAnchor(nextState)
    {
        self.Enter(nextState, "launch_pending");
        self._scout.AimAt(self._anchor);
        if (self._leg == 1 && !self._recovering)
        {
            self._scout.Jump();
        }
        self._attempts = self._attempts + 1;
        self._scout.LaunchHookLeft(self._anchor);
        self.Emit("hook_launch", "mode=" + self._anchorMode + " anchor=" + Convert.ToString(self._anchor));
    }

    function AttachStep(timeout, recovery)
    {
        if (Time.GameTime - self._stateStart >= timeout)
        {
            if (recovery)
            {
                self.Terminate("safe_termination", "recovery_attachment_timeout");
            }
            else
            {
                self.Enter("RecoverPlan", "attachment_timeout");
            }
            return;
        }
        if (self._scout.IsHookedLeft)
        {
            self._attachments = self._attachments + 1;
            if (recovery)
            {
                self.Enter("RecoverBurst", "hook_attached");
                self._scout.UseGas(true);
                self.Emit("hook_attached", "mode=recovery");
            }
            else
            {
                self.Enter("Burst", "hook_attached");
                self._scout.UseGas(true);
                self.Emit("hook_attached", "mode=primary");
            }
        }
    }

    function BurstStep(limit, recovery)
    {
        if (!self._scout.IsHookedLeft)
        {
            if (recovery)
            {
                self.Terminate("safe_termination", "recovery_hook_lost");
            }
            else
            {
                self.Enter("RecoverPlan", "hook_lost");
            }
            return;
        }
        if (Vector3.Distance(self._scout.Position, self._anchor) <= 10.0 || Time.GameTime - self._stateStart >= limit)
        {
            self.StopODM();
            self.Emit("hook_release", "mode=" + self._anchorMode);
            if (recovery)
            {
                self.Enter("Observe", "recovery_release");
            }
            elif (self._leg == 1)
            {
                self.Enter("Coast", "leg1_release");
                self._coastSpeedLowAt = -1.0;
            }
            else
            {
                self.Enter("Observe", "leg2_release");
            }
        }
    }

    function CoastStep()
    {
        if (Time.GameTime - self._stateStart >= 1.0)
        {
            self.Enter("RecoverPlan", "coast_deadline");
            return;
        }
        velocity = self._scout.Velocity;
        horizontal = Vector3(velocity.X, 0.0, velocity.Z);
        if (horizontal.Magnitude < 6.0)
        {
            if (self._coastSpeedLowAt < 0.0)
            {
                self._coastSpeedLowAt = Time.GameTime;
            }
            elif (Time.GameTime - self._coastSpeedLowAt >= 0.25)
            {
                self.Enter("RecoverPlan", "momentum_lost");
                return;
            }
        }
        else
        {
            self._coastSpeedLowAt = -1.0;
        }
        if (self._scout.LeftHookReady && !self._scout.IsHookedLeft && Time.GameTime - self._stateStart >= 0.12)
        {
            self.BeginTraversalLeg();
        }
    }

    function ObserveStep()
    {
        if (Time.GameTime - self._stateStart >= self.ObserveSeconds)
        {
            if (self._recoveries > 0)
            {
                self.Terminate("success", "completed_with_recovery");
            }
            else
            {
                self.Terminate("success", "completed");
            }
            return;
        }
        if (self._recoveries >= self.MaxRecoveryAttempts)
        {
            return;
        }
        velocity = self._scout.Velocity;
        if (velocity.Y <= -28.0 && velocity.Magnitude >= 30.0 && self._scout.CurrentGas >= self.RecoveryGasReserve && self._scout.LeftHookReady && !self._scout.IsHookedLeft)
        {
            self.Enter("RecoverPlan", "dangerous_fall");
        }
    }

    function ConsiderAnchor(direction, rise)
    {
        start = self._scout.Position + Vector3(0.0, 3.0, 0.0);
        ray = Vector3.Normalize(direction * self.HookReach + Vector3(0.0, rise, 0.0));
        hit = self.MapHit(start, start + ray * self.HookReach);
        if (hit == null)
        {
            self.LogReject("ray_miss");
            return;
        }
        delta = hit.Point - self._scout.Position;
        distance = delta.Magnitude;
        if (distance < 15.0)
        {
            self.LogReject("too_near");
            return;
        }
        if (distance > self.HookReach)
        {
            self.LogReject("out_of_reach");
            return;
        }
        if (delta.Y < 4.0)
        {
            self.LogReject("too_low");
            return;
        }
        if (delta.Y > 42.0)
        {
            self.LogReject("too_high");
            return;
        }
        if (self._previousAnchor != null && Vector3.Distance(hit.Point, self._previousAnchor) < 12.0)
        {
            self.LogReject("too_close_to_previous");
            return;
        }
        horizontal = Vector3(delta.X, 0.0, delta.Z);
        if (horizontal.Magnitude < 0.1)
        {
            self.LogReject("vertical_only");
            return;
        }
        alignment = Vector3.Dot(horizontal.Normalized, self._direction);
        if (alignment < 0.35)
        {
            self.LogReject("poor_alignment");
            return;
        }
        if (self.BodyClearanceBlocked(horizontal.Normalized))
        {
            self.LogReject("body_clearance_blocked");
            return;
        }
        if (self.IntermediateCollisionRisk(delta))
        {
            self.LogReject("intermediate_obstacle");
            return;
        }
        if (self.ExitPathBlocked(hit.Point, horizontal.Normalized))
        {
            self.LogReject("exit_blocked");
            return;
        }
        score = alignment * 55.0 + distance * 0.2 + delta.Y * 0.08;
        if (self._recovering)
        {
            score = score + delta.Y * 0.12;
        }
        if (score > self._bestScore)
        {
            self._anchor = hit.Point;
            self._bestScore = score;
        }
    }

    function BodyClearanceBlocked(direction)
    {
        start = self._scout.Position + Vector3(0.0, 1.0, 0.0);
        end = start + direction * 4.0;
        hit = self.MapHit(start, end);
        return hit != null && hit.Distance <= 3.5;
    }

    function IntermediateCollisionRisk(delta)
    {
        start = self._scout.Position + Vector3(0.0, 1.0, 0.0);
        end = start + delta * 0.55;
        hit = self.MapHit(start, end);
        return hit != null && hit.Distance <= delta.Magnitude * 0.5;
    }

    function ExitPathBlocked(anchor, horizontalDir)
    {
        start = anchor + Vector3(0.0, 1.0, 0.0);
        end = start + horizontalDir * 8.0;
        hit = self.MapHit(start, end);
        return hit != null && hit.Distance <= 6.0;
    }

    function LogReject(reason)
    {
        if (self._legRejectLogs < 8)
        {
            self._legRejectLogs = self._legRejectLogs + 1;
            self.Emit("anchor_reject", "mode=" + self._anchorMode + " reason=" + reason);
        }
    }

    function MapHit(start, end)
    {
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

    function Enter(state, reason)
    {
        oldState = self._state;
        self._state = state;
        self._stateStart = Time.GameTime;
        self.Emit("state_transition", "from=" + oldState + " to=" + state + " reason=" + reason);
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

    function Emit(event, details)
    {
        if (!self.Diagnostics || self._logCount >= 160)
        {
            return;
        }
        self._logCount = self._logCount + 1;
        Game.Print("[AI Cadets M1R] t=" + Convert.ToString(Time.GameTime) + " state=" + self._state + " leg=" + Convert.ToString(self._leg) + " event=" + event + " " + details);
    }

    function Terminate(resultClass, reason)
    {
        self.StopODM();
        if (self._state == "Done")
        {
            return;
        }
        self._lastResultClass = resultClass;
        self._lastResultReason = reason;
        displacement = "n/a";
        gasUsed = "n/a";
        if (self._initialPosition != null && self._lastPosition != null)
        {
            displacement = Convert.ToString(Vector3.Distance(self._lastPosition, self._initialPosition));
            gasUsed = Convert.ToString(self._initialGas - self._lastGas);
        }
        self.Emit("termination", "class=" + resultClass + " reason=" + reason);
        Game.Print("[AI Cadets M1R] result_class=" + resultClass + " result_reason=" + reason + " state=" + self._state + " leg=" + Convert.ToString(self._leg) + " attempts=" + Convert.ToString(self._attempts) + " attachments=" + Convert.ToString(self._attachments) + " recoveries=" + Convert.ToString(self._recoveries) + " displacement=" + displacement + " gas_used=" + gasUsed + " (last live sample)");
        self.Enter("Done", "terminated");
    }
}
