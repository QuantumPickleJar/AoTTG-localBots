# M2 experimental Wave-mode cadet controller.
# Preserves M1 add-ons as rollback baseline; this is a separate addon.
addon AICadetsWaveCadet
{
    Description = "M2 experiment: autonomous Wave-mode titan target acquisition, ODM approach, strike, retreat, and bounded recovery.";

    SpawnSide = 4.0;
    MinGasReserve = 10.0;
    MinAttackGas = 14.0;
    HookReach = 70.0;
    AnchorRise = 12.0;
    BurstSeconds = 0.55;
    AttackHoldSeconds = 0.30;
    AttackRange = 10.5;
    ApproachBehindDistance = 17.0;
    ApproachHeight = 6.0;
    RetreatDistance = 24.0;
    TraverseProgressMin = 4.0;
    MaxTraversePerTarget = 30;
    MaxTargetRetries = 3;
    MaxRecoveriesPerTarget = 2;
    Diagnostics = true;
    SaveRunReport = false;

    _started = false;
    _eligible = false;
    _state = "Dormant";
    _stateStart = 0.0;
    _runStart = 0.0;
    _nextTickReport = 0.0;
    _noTargetCooldownUntil = 0.0;
    _cadet = null;
    _cadetName = "";
    _runId = "";

    _target = null;
    _targetViewId = 0;
    _targetRetryCount = 0;
    _targetTraverseCount = 0;
    _targetRecoveries = 0;
    _targetDamaged = false;
    _targetKilled = false;
    _bannedTargetViewId = 0;
    _banUntil = 0.0;
    _lastDistanceToNape = 0.0;
    _lastFailureReason = "none";

    _traverseMode = "none";
    _traverseGoal = null;
    _trLeg = 0;
    _trStartDistance = 0.0;
    _trStartPosition = null;
    _trOutcome = "none";
    _anchor = null;
    _previousAnchor = null;
    _bestScore = -100000.0;
    _direction = null;
    _nextRiskCheck = 0.0;

    _killsObserved = 0;
    _titanDeathsObserved = 0;
    _damageEvents = 0;
    _logCount = 0;
    _trace = "";
    _reportSaved = false;

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
        self._runId = "m2-" + Convert.ToString(Time.GameTime);
        self.Enter("WaitHost", "startup");
        self.LogEvent("ready", "run_id=" + self._runId + " host_timeout=30");
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
            self.SpawnCadet(host);
            return;
        }
        if (self._cadet == null)
        {
            self.Terminate("safe_termination", "cadet_missing");
            return;
        }
        if (!self._cadet.IsMine)
        {
            self.Terminate("safe_termination", "ownership_lost_cleanup_unavailable");
            return;
        }
        if (!self._cadet.IsAlive)
        {
            self.Terminate("safe_termination", "cadet_dead");
            return;
        }
        if (self._cadet.CurrentGas <= self.MinGasReserve)
        {
            self.Terminate("safe_termination", "insufficient_odm_resources");
            return;
        }
        if (Game.IsEnding)
        {
            self.Terminate("safe_termination", "game_ending");
            return;
        }
        if (Time.GameTime >= self._nextTickReport)
        {
            self._nextTickReport = Time.GameTime + 5.0;
            self.LogEvent("mission_snapshot", "titans=" + Convert.ToString(Game.Titans.Count) + " humans=" + Convert.ToString(Game.Humans.Count) + " player_humans=" + Convert.ToString(Game.PlayerHumans.Count));
        }
        if (self.IsTraverseState() && Time.GameTime >= self._nextRiskCheck)
        {
            self._nextRiskCheck = Time.GameTime + 0.1;
            if (self.CollisionRisk())
            {
                self._trOutcome = "collision_risk";
                self.FinishTraverse();
                return;
            }
        }

        if (self._state == "Regroup")
        {
            if (Time.GameTime - self._stateStart >= 0.35 && Time.GameTime >= self._noTargetCooldownUntil)
            {
                self.Enter("AcquireTarget", "regroup_complete");
            }
            return;
        }
        if (self._state == "AcquireTarget")
        {
            self.AcquireTarget();
            return;
        }
        if (self._state == "PlanApproach")
        {
            self.PlanApproach();
            return;
        }
        if (self._state == "TraverseAttach")
        {
            self.TraverseAttachStep();
            return;
        }
        if (self._state == "TraverseBurst")
        {
            self.TraverseBurstStep();
            return;
        }
        if (self._state == "TraverseCoast")
        {
            self.TraverseCoastStep();
            return;
        }
        if (self._state == "AttackSetup")
        {
            self.AttackSetupStep();
            return;
        }
        if (self._state == "Strike")
        {
            self.StrikeStep();
            return;
        }
        if (self._state == "VerifyAttack")
        {
            self.VerifyAttackStep();
            return;
        }
        if (self._state == "Retreat")
        {
            self.RetreatStep();
            return;
        }
        if (self._state == "Recover")
        {
            self.RecoverStep();
            return;
        }
        self.Terminate("failure", "invalid_state");
    }

    function OnCharacterDamaged(victim, killer, killerName, damage)
    {
        if (!self._eligible || self._state == "Done")
        {
            return;
        }
        if (victim == null || victim.Type != "Titan")
        {
            return;
        }
        if (self._targetViewId != 0 && victim.ViewID == self._targetViewId)
        {
            self._targetDamaged = true;
            self._damageEvents = self._damageEvents + 1;
            byCadet = false;
            if (killer != null && self._cadet != null && killer.ViewID == self._cadet.ViewID)
            {
                byCadet = true;
            }
            self.LogEvent("target_damaged", "view_id=" + Convert.ToString(victim.ViewID) + " damage=" + Convert.ToString(damage) + " by_cadet=" + Convert.ToString(byCadet));
        }
    }

    function OnCharacterDie(victim, killer, killerName)
    {
        if (!self._eligible || self._state == "Done")
        {
            return;
        }
        if (victim == null)
        {
            return;
        }
        if (victim.Type == "Titan")
        {
            self._titanDeathsObserved = self._titanDeathsObserved + 1;
            byCadet = false;
            if (killer != null && self._cadet != null && killer.ViewID == self._cadet.ViewID)
            {
                byCadet = true;
                self._killsObserved = self._killsObserved + 1;
            }
            if (self._targetViewId != 0 && victim.ViewID == self._targetViewId)
            {
                self._targetKilled = true;
            }
            self.LogEvent("titan_die", "victim=" + Convert.ToString(victim.ViewID) + " by_cadet=" + Convert.ToString(byCadet) + " killer_name=" + killerName);
            return;
        }
        if (self._cadet != null && victim.ViewID == self._cadet.ViewID)
        {
            self.Terminate("safe_termination", "cadet_killed");
        }
    }

    function SpawnCadet(host)
    {
        if (self.HookReach < 20.0 || self.HookReach > 70.0 || self.AnchorRise < 4.0 || self.AnchorRise > 25.0 || self.BurstSeconds < 0.1 || self.BurstSeconds > 0.8 || self.MinGasReserve < 4.0 || self.MinAttackGas <= self.MinGasReserve || self.AttackRange < 6.0 || self.AttackRange > 18.0 || self.MaxTraversePerTarget < 1 || self.MaxTraversePerTarget > 40 || self.MaxTargetRetries < 1 || self.MaxTargetRetries > 6 || self.MaxRecoveriesPerTarget < 0 || self.MaxRecoveriesPerTarget > 4)
        {
            self.Terminate("failure", "invalid_settings");
            return;
        }
        self._cadetName = self.FindCadetName();
        if (self._cadetName == "")
        {
            self.Terminate("safe_termination", "cadet_name_unavailable");
            return;
        }
        spawnPos = host.Position + host.Right * self.SpawnSide;
        if (self.MapHit(host.Position + Vector3(0.0, 1.0, 0.0), spawnPos + Vector3(0.0, 1.0, 0.0)) != null)
        {
            self.Terminate("safe_termination", "spawn_path_blocked");
            return;
        }
        self.Enter("Done", "spawn_latched");
        self._cadet = Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades, spawnPos, 0.0);
        if (self._cadet == null || !self._cadet.IsMine || !self._cadet.IsAlive)
        {
            self.StopODM();
            Game.Print("[AI Cadets M2] result_class=failure result_reason=spawn_failed_or_not_owned run_id=" + self._runId);
            return;
        }
        self._cadet.Name = self._cadetName;
        self._cadet.SetDisplayName(self._cadetName, true);
        self._cadet.Idle();
        self._direction = Vector3.Normalize(Vector3(host.Forward.X, 0.0, host.Forward.Z));
        self.LogEvent("cadet_spawned", "name=" + self._cadetName + " view_id=" + Convert.ToString(self._cadet.ViewID));
        self.Enter("Regroup", "spawned");
    }

    function FindCadetName()
    {
        for (i in Range(1, 5, 1))
        {
            candidate = "AICadetsM2-" + Convert.ToString(i);
            used = false;
            for (human in Game.AIHumans)
            {
                if (human.IsAlive && human.Name == candidate)
                {
                    used = true;
                }
            }
            if (!used)
            {
                return candidate;
            }
        }
        return "";
    }

    # Search all existing live Titans, not only those within a fixed combat radius.
    # A distant valid target is a navigation goal; proximity should affect approach,
    # not whether the target exists.
    function AcquireTarget()
    {
        self._target = null;
        self._targetViewId = 0;
        self._targetDamaged = false;
        self._targetKilled = false;
        best = -1000000.0;
        listed = 0;
        alive = 0;
        banned = 0;
        nearest = -1.0;
        for (titan in Game.Titans)
        {
            listed = listed + 1;
            if (!titan.IsAlive)
            {
                continue;
            }
            alive = alive + 1;
            toNape = titan.NapePosition - self._cadet.Position;
            distance = toNape.Magnitude;
            if (nearest < 0.0 || distance < nearest)
            {
                nearest = distance;
            }
            if (self._bannedTargetViewId != 0 && titan.ViewID == self._bannedTargetViewId && Time.GameTime < self._banUntil)
            {
                banned = banned + 1;
                continue;
            }
            score = 260.0 - distance;
            if (titan.IsCrawler)
            {
                score = score - 12.0;
            }
            if (toNape.Y < 2.0)
            {
                score = score - 8.0;
            }
            if (score > best)
            {
                best = score;
                self._target = titan;
                self._targetViewId = titan.ViewID;
            }
        }
        if (self._target == null)
        {
            reason = "no_alive_titans";
            if (alive > 0 && banned > 0)
            {
                reason = "all_candidates_temporarily_banned";
            }
            self.LogEvent("target_none", "reason=" + reason + " listed=" + Convert.ToString(listed) + " alive=" + Convert.ToString(alive) + " banned=" + Convert.ToString(banned) + " nearest=" + Convert.ToString(nearest));
            # Leave room for wave spawns / temporary target bans without 3 log lines
            # every 0.35 seconds, which previously exhausted the 260-print budget.
            self._noTargetCooldownUntil = Time.GameTime + 2.5;
            self.Enter("Regroup", "no_target");
            return;
        }
        self._noTargetCooldownUntil = 0.0;
        self._targetRetryCount = 0;
        self._targetTraverseCount = 0;
        self._targetRecoveries = 0;
        self._lastDistanceToNape = Vector3.Distance(self._cadet.Position, self._target.NapePosition);
        self.LogEvent("target_selected", "view_id=" + Convert.ToString(self._targetViewId) + " distance=" + Convert.ToString(self._lastDistanceToNape) + " listed=" + Convert.ToString(listed) + " alive=" + Convert.ToString(alive));
        self.Enter("PlanApproach", "target_selected");
    }

    function PlanApproach()
    {
        if (!self.RefreshTarget())
        {
            self.Enter("AcquireTarget", "target_invalid");
            return;
        }
        nape = self._target.NapePosition;
        delta = nape - self._cadet.Position;
        self._lastDistanceToNape = delta.Magnitude;
        if (self._lastDistanceToNape <= self.AttackRange && self._cadet.CurrentGas >= self.MinAttackGas)
        {
            self.Enter("AttackSetup", "attack_window");
            return;
        }
        if (self._targetTraverseCount >= self.MaxTraversePerTarget)
        {
            self.Enter("Recover", "traverse_budget_exhausted");
            return;
        }
        behindDir = Vector3.Normalize(Vector3(self._target.Forward.X, 0.0, self._target.Forward.Z));
        if (behindDir.Magnitude < 0.1)
        {
            behindDir = Vector3.Normalize(Vector3(delta.X, 0.0, delta.Z)) * -1.0;
        }
        goal = nape - behindDir * self.ApproachBehindDistance + Vector3(0.0, self.ApproachHeight, 0.0);
        self.StartTraverse(goal, "approach");
    }

    function StartTraverse(goal, mode)
    {
        if (!self._cadet.LeftHookReady)
        {
            self.Enter("Recover", "hook_not_ready");
            return;
        }
        self._traverseGoal = goal;
        self._traverseMode = mode;
        self._trLeg = 0;
        self._trOutcome = "none";
        self._previousAnchor = self._anchor;
        self._trStartDistance = 0.0;
        if (self._target != null && self._target.IsAlive)
        {
            self._trStartDistance = Vector3.Distance(self._cadet.Position, self._target.NapePosition);
        }
        self._trStartPosition = self._cadet.Position;
        self.LogEvent("traverse_start", "mode=" + mode + " goal=" + Convert.ToString(goal) + " target_dist=" + Convert.ToString(self._trStartDistance) + " attempts=" + Convert.ToString(self._targetTraverseCount));
        self.BeginTraverseLeg();
    }

    function BeginTraverseLeg()
    {
        self._trLeg = self._trLeg + 1;
        velocity = self._cadet.Velocity;
        horizontalVelocity = Vector3(velocity.X, 0.0, velocity.Z);
        toGoal = self._traverseGoal - self._cadet.Position;
        baseDirection = Vector3.Normalize(Vector3(toGoal.X, 0.0, toGoal.Z));
        # Blend existing momentum with goal bearing so the second leg remains
        # target-directed. Following velocity alone can steer away from a Titan.
        self._direction = baseDirection;
        if (self._trLeg == 2 && horizontalVelocity.Magnitude >= 2.0)
        {
            self._direction = Vector3.Normalize(baseDirection * 0.8 + horizontalVelocity.Normalized * 0.2);
        }
        self._anchor = null;
        self._bestScore = -100000.0;
        right = Vector3(self._direction.Z, 0.0, 0.0 - self._direction.X);
        rise = self.AnchorRise;
        if (self._trLeg == 2)
        {
            rise = self.AnchorRise * 1.8;
        }
        self.ConsiderAnchor(self._direction, rise);
        self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 0.45), rise);
        self.ConsiderAnchor(Vector3.Normalize(self._direction - right * 0.45), rise);
        self.ConsiderAnchor(self._direction, rise * 1.6);
        self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 0.8), rise);
        # City streets often have no forward-facing hookable wall; search
        # both lateral building facades before abandoning a long-range goal.
        if (self._anchor == null)
        {
            self.ConsiderAnchor(Vector3.Normalize(self._direction - right * 0.8), rise);
            self.ConsiderAnchor(Vector3.Normalize(self._direction + right * 1.8), rise);
            self.ConsiderAnchor(Vector3.Normalize(self._direction - right * 1.8), rise);
        }
        if (self._anchor == null)
        {
            self.LogEvent("anchor_search_failed", "goal=" + Convert.ToString(self._traverseGoal) + " position=" + Convert.ToString(self._cadet.Position) + " leg=" + Convert.ToString(self._trLeg));
            self._trOutcome = "no_suitable_anchor";
            self.FinishTraverse();
            return;
        }
        self.Enter("TraverseAttach", "hook_launch");
        self._cadet.AimAt(self._anchor);
        if (self._trLeg == 1)
        {
            self._cadet.Jump();
        }
        self._cadet.LaunchHookLeft(self._anchor);
        self.LogEvent("hook_launch", "mode=" + self._traverseMode + " leg=" + Convert.ToString(self._trLeg) + " anchor=" + Convert.ToString(self._anchor));
    }

    function TraverseAttachStep()
    {
        if (Time.GameTime - self._stateStart >= 2.8)
        {
            self._trOutcome = "attachment_timeout";
            self.FinishTraverse();
            return;
        }
        if (self._cadet.IsHookedLeft)
        {
            self._cadet.UseGas(true);
            self.Enter("TraverseBurst", "hook_attached");
            self.LogEvent("hook_attached", "mode=" + self._traverseMode + " leg=" + Convert.ToString(self._trLeg));
        }
    }

    function TraverseBurstStep()
    {
        if (!self._cadet.IsHookedLeft)
        {
            self._trOutcome = "hook_lost";
            self.FinishTraverse();
            return;
        }
        if (Vector3.Distance(self._cadet.Position, self._anchor) <= 10.0 || Time.GameTime - self._stateStart >= self.BurstSeconds)
        {
            self.StopODM();
            self.LogEvent("hook_release", "mode=" + self._traverseMode + " leg=" + Convert.ToString(self._trLeg));
            if (self._trLeg == 1)
            {
                self.Enter("TraverseCoast", "leg1_release");
            }
            else
            {
                self._trOutcome = "completed";
                self.FinishTraverse();
            }
        }
    }

    function TraverseCoastStep()
    {
        if (Time.GameTime - self._stateStart >= 1.0)
        {
            self._trOutcome = "coast_timeout";
            self.FinishTraverse();
            return;
        }
        if (self._cadet.LeftHookReady && !self._cadet.IsHookedLeft && Time.GameTime - self._stateStart >= 0.12)
        {
            self.BeginTraverseLeg();
        }
    }

    function FinishTraverse()
    {
        self.StopODM();
        self._targetTraverseCount = self._targetTraverseCount + 1;
        self.LogEvent("traverse_end", "mode=" + self._traverseMode + " outcome=" + self._trOutcome + " legs=" + Convert.ToString(self._trLeg));
        if (self._traverseMode == "retreat")
        {
            self.Enter("Regroup", "retreat_complete");
            return;
        }
        if (self._traverseMode == "recover")
        {
            self.Enter("PlanApproach", "recover_complete");
            return;
        }
        if (!self.RefreshTarget())
        {
            self.Enter("AcquireTarget", "target_lost_after_traverse");
            return;
        }
        nowDistance = Vector3.Distance(self._cadet.Position, self._target.NapePosition);
        progress = self._trStartDistance - nowDistance;
        self.LogEvent("progress", "delta=" + Convert.ToString(progress) + " dist=" + Convert.ToString(nowDistance));
        if (self._trOutcome == "completed" && nowDistance <= self.AttackRange && self._cadet.CurrentGas >= self.MinAttackGas)
        {
            self.Enter("AttackSetup", "traverse_attack_window");
            return;
        }
        if (progress >= self.TraverseProgressMin)
        {
            self._targetRetryCount = 0;
            self.Enter("PlanApproach", "progress_ok");
            return;
        }
        self._targetRetryCount = self._targetRetryCount + 1;
        self._lastFailureReason = self._trOutcome;
        if (self._targetRetryCount > self.MaxTargetRetries)
        {
            self._bannedTargetViewId = self._targetViewId;
            self._banUntil = Time.GameTime + 4.0;
            self.LogEvent("target_banned", "view_id=" + Convert.ToString(self._targetViewId) + " reason=" + self._lastFailureReason);
            self.Enter("AcquireTarget", "retry_exhausted");
            return;
        }
        self.Enter("Recover", "insufficient_progress");
    }

    function AttackSetupStep()
    {
        if (!self.RefreshTarget())
        {
            self.Enter("AcquireTarget", "target_lost_attack_setup");
            return;
        }
        distance = Vector3.Distance(self._cadet.Position, self._target.NapePosition);
        if (distance > self.AttackRange + 2.0)
        {
            self.Enter("PlanApproach", "attack_window_lost");
            return;
        }
        self._cadet.AimAt(self._target.NapePosition);
        self._cadet.Attack(true);
        self._targetDamaged = false;
        self._targetKilled = false;
        self.Enter("Strike", "attack_started");
        self.LogEvent("attack_attempt", "target=" + Convert.ToString(self._targetViewId) + " dist=" + Convert.ToString(distance));
    }

    function StrikeStep()
    {
        if (Time.GameTime - self._stateStart >= self.AttackHoldSeconds || self._targetKilled)
        {
            self._cadet.Attack(false);
            self.Enter("VerifyAttack", "attack_released");
        }
    }

    function VerifyAttackStep()
    {
        if (!self.RefreshTarget())
        {
            self._targetKilled = true;
        }
        if (self._targetKilled)
        {
            self.LogEvent("attack_result", "confirmed_kill=true target=" + Convert.ToString(self._targetViewId));
            self.Enter("AcquireTarget", "target_killed");
            return;
        }
        if (self._targetDamaged)
        {
            self.LogEvent("attack_result", "confirmed_damage=true target=" + Convert.ToString(self._targetViewId));
        }
        else
        {
            self.LogEvent("attack_result", "confirmed_damage=false target=" + Convert.ToString(self._targetViewId));
        }
        self.Enter("Retreat", "post_attack");
    }

    function RetreatStep()
    {
        if (!self.RefreshTarget())
        {
            self.Enter("Regroup", "retreat_no_target");
            return;
        }
        away = self._cadet.Position - self._target.Position;
        horizontalAway = Vector3.Normalize(Vector3(away.X, 0.0, away.Z));
        if (horizontalAway.Magnitude < 0.1)
        {
            horizontalAway = Vector3.Normalize(Vector3(self._cadet.Forward.X, 0.0, self._cadet.Forward.Z)) * -1.0;
        }
        retreatPoint = self._cadet.Position + horizontalAway * self.RetreatDistance + Vector3(0.0, 4.0, 0.0);
        self.StartTraverse(retreatPoint, "retreat");
    }

    function RecoverStep()
    {
        if (self._targetRecoveries >= self.MaxRecoveriesPerTarget)
        {
            self.LogEvent("recover_exhausted", "target=" + Convert.ToString(self._targetViewId) + " reason=" + self._lastFailureReason);
            self._bannedTargetViewId = self._targetViewId;
            self._banUntil = Time.GameTime + 4.0;
            self.Enter("AcquireTarget", "recover_budget_exhausted");
            return;
        }
        if (!self._cadet.LeftHookReady || self._cadet.CurrentGas < self.MinAttackGas)
        {
            self.Terminate("safe_termination", "recovery_unavailable_resources");
            return;
        }
        self._targetRecoveries = self._targetRecoveries + 1;
        velocity = self._cadet.Velocity;
        horizontalVelocity = Vector3(velocity.X, 0.0, velocity.Z);
        if (horizontalVelocity.Magnitude >= 1.0)
        {
            self._direction = horizontalVelocity.Normalized;
        }
        else
        {
            self._direction = Vector3.Normalize(Vector3(self._cadet.Forward.X, 0.0, self._cadet.Forward.Z));
        }
        # After a blocked/empty forward corridor, try a different lateral
        # approach on each bounded recovery attempt instead of repeating the
        # same heading and getting the same no-anchor result.
        if (self._target != null && self._target.IsAlive)
        {
            toTarget = self._target.NapePosition - self._cadet.Position;
            flatTarget = Vector3(toTarget.X, 0.0, toTarget.Z);
            if (flatTarget.Magnitude >= 1.0)
            {
                self._direction = flatTarget.Normalized;
            }
        }
        right = Vector3(self._direction.Z, 0.0, 0.0 - self._direction.X);
        if (self._targetRecoveries == 1)
        {
            self._direction = Vector3.Normalize(self._direction + right * 0.8);
        }
        else
        {
            self._direction = Vector3.Normalize(self._direction - right * 0.8);
        }
        recoverGoal = self._cadet.Position + self._direction * 30.0 + Vector3(0.0, 10.0, 0.0);
        self.StartTraverse(recoverGoal, "recover");
    }

    function RefreshTarget()
    {
        if (self._targetViewId == 0)
        {
            return false;
        }
        for (titan in Game.Titans)
        {
            if (titan.ViewID == self._targetViewId)
            {
                if (!titan.IsAlive)
                {
                    return false;
                }
                self._target = titan;
                return true;
            }
        }
        return false;
    }

    function ConsiderAnchor(direction, rise)
    {
        start = self._cadet.Position + Vector3(0.0, 3.0, 0.0);
        ray = Vector3.Normalize(direction * self.HookReach + Vector3(0.0, rise, 0.0));
        hit = self.MapHit(start, start + ray * self.HookReach);
        if (hit == null)
        {
            return;
        }
        delta = hit.Point - self._cadet.Position;
        distance = delta.Magnitude;
        if (distance < 15.0 || distance > self.HookReach || delta.Y < 4.0 || delta.Y > 42.0)
        {
            return;
        }
        if (self._previousAnchor != null && Vector3.Distance(hit.Point, self._previousAnchor) < 12.0)
        {
            return;
        }
        horizontal = Vector3(delta.X, 0.0, delta.Z);
        if (horizontal.Magnitude < 0.1)
        {
            return;
        }
        alignment = Vector3.Dot(horizontal.Normalized, self._direction);
        # Lateral anchors are permissible when they still move the cadet
        # at least slightly toward the current travel bearing.
        if (alignment < 0.05)
        {
            return;
        }
        score = alignment * 55.0 + distance * 0.25 + delta.Y * 0.05;
        if (score > self._bestScore)
        {
            self._anchor = hit.Point;
            self._bestScore = score;
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
        velocity = self._cadet.Velocity;
        if (velocity.Magnitude < 2.0)
        {
            return false;
        }
        start = self._cadet.Position + Vector3(0.0, 1.0, 0.0);
        end = start + velocity * 0.2 + velocity.Normalized * 2.0;
        return self.MapHit(start, end) != null;
    }

    function IsTraverseState()
    {
        return self._state == "TraverseAttach" || self._state == "TraverseBurst" || self._state == "TraverseCoast";
    }

    function Enter(state, reason)
    {
        oldState = self._state;
        self._state = state;
        self._stateStart = Time.GameTime;
        self.LogEvent("state_transition", "from=" + oldState + " to=" + state + " reason=" + reason);
    }

    function StopODM()
    {
        if (Network.IsMasterClient && self._cadet != null && self._cadet.IsMine)
        {
            self._cadet.UseGas(false);
            self._cadet.Attack(false);
            self._cadet.ReleaseHookLeft();
            self._cadet.ReleaseHookRight();
        }
    }

    function LogEvent(event, details)
    {
        line = "t=" + Convert.ToString(Time.GameTime) + " run=" + self._runId + " cadet=" + self._cadetName + " state=" + self._state + " target=" + Convert.ToString(self._targetViewId) + " event=" + event + " " + details;
        self._trace = self._trace + line + "\n";
        if (!self.Diagnostics || self._logCount >= 260)
        {
            return;
        }
        self._logCount = self._logCount + 1;
        Game.Print("[AI Cadets M2] " + line);
    }

    function SaveReportIfEnabled()
    {
        if (!self.SaveRunReport || self._reportSaved)
        {
            return;
        }
        self._reportSaved = true;
        PersistentData.SetProperty("AICadetsM2Report", self._trace);
        PersistentData.SaveToFile("AICadetsM2Report_" + self._runId, false);
    }

    function Terminate(resultClass, reason)
    {
        self.StopODM();
        if (self._state == "Done")
        {
            return;
        }
        self.LogEvent("termination", "result_class=" + resultClass + " reason=" + reason + " kills_observed=" + Convert.ToString(self._killsObserved) + " titan_deaths_observed=" + Convert.ToString(self._titanDeathsObserved) + " damage_events=" + Convert.ToString(self._damageEvents));
        Game.Print("[AI Cadets M2] result_class=" + resultClass + " result_reason=" + reason + " run_id=" + self._runId + " cadet=" + self._cadetName + " target_retry=" + Convert.ToString(self._targetRetryCount) + " target_traverses=" + Convert.ToString(self._targetTraverseCount) + " target_recoveries=" + Convert.ToString(self._targetRecoveries) + " kills_observed=" + Convert.ToString(self._killsObserved) + " titan_deaths_observed=" + Convert.ToString(self._titanDeathsObserved));
        self.SaveReportIfEnabled();
        self.Enter("Done", "terminated");
    }
}
