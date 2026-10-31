# M2 experimental Wave-mode cadet controller.
# Preserves M1 add-ons as rollback baseline; this is a separate addon.
addon AICadetsWaveCadet
{
    Description = "M2 experiment: autonomous Wave-mode titan target acquisition, ODM approach, strike, retreat, and bounded recovery.";

    _buildTag = "M2-navdiag-1";
    GroundSteering = "Engine";
    ProfileName = "Steady scout";
    Persistence = 3;
    AerialPreference = 3;
    RepositionSkill = 3;
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
    MaxRecoveriesPerTarget = 4;
    ExploreSegmentDistance = 58.0;
    ExploreScanSeconds = 2.5;
    ExploreGroundSeconds = 9.0;
    GroundApproachThreshold = 68.0;
    GroundProgressWindow = 5.0;
    ResupplyTriggerGas = 38.0;
    SupplyArrivalRange = 2.0;
    SupplySearchTimeout = 100.0;
    SupplyRefillTimeout = 12.0;
    Diagnostics = true;
    SaveRunReport = false;
    RecordDecisionTrace = true;

    _started = false;
    _spawnLatched = false;
    _eligible = false;
    _terminationReason = "none";
    _lastPublishedState = "Dormant";
    _state = "Dormant";
    _stateStart = 0.0;
    _runStart = 0.0;
    _nextTickReport = 0.0;
    _noTargetCooldownUntil = 0.0;
    _exploreNextScan = 0.0;
    _exploreNextAction = 0.0;
    _exploreIndex = 0;
    _exploreDirection = null;
    _exploreStartPosition = null;
    _exploreFailures = 0;
    _groundGoal = null;
    _groundStartPosition = null;
    _groundProgressPosition = null;
    _groundMovementStartedAt = 0.0;
    _groundNextCheck = 0.0;
    _groundStalledChecks = 0;
    _groundFallback = false;
    _groundBearing = null;
    _nextTravelProbe = 0.0;
    _orderSequence = 0;
    _orderMode = "Engage";
    _nextOrderStatus = 0.0;
    _lastAppliedOrderSequence = 0;
    _resumeAfterSupply = "Engage";
    _supplyPoint = null;
    _supplySource = "none";
    _supplySearchStarted = 0.0;
    _supplyArrivalStarted = 0.0;
    _supplyScanDue = 0.0;
    _supplyMoveDue = 0.0;
    _supplyLastProgressAt = 0.0;
    _supplyLastPosition = null;
    _supplyWaypoint = null;
    _supplyDetour = 0;
    _supplyGasBefore = 0.0;
    _supplyAutoRefillBefore = false;
    _supplyMarkVersion = 0;
    _cadet = null;
    _cadetName = "";
    _runId = "";

    _target = null;
    _targetViewId = 0;
    _targetRetryCount = 0;
    _targetTraverseCount = 0;
    _targetRecoveries = 0;
    _targetDamaged = false;
    _targetDamageByCadet = false;
    _targetKilled = false;
    _targetKillByCadet = false;
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
    _eventId = 0;
    _trace = "";
    _reportSaved = false;

    function OnGameStart()
    {
        if (self._started)
        {
            # Game/mode callbacks may be repeated. They must not kill an
            # already owned and functioning WaveCadet controller.
            self.LogEvent("duplicate_start_ignored", "state=" + self._state);
            return;
        }
        self._started = true;
        self._eligible = Network.IsMasterClient;
        if (!self._eligible)
        {
            return;
        }
        if ((self.GroundSteering != "Engine" && self.GroundSteering != "Direct") || self.Persistence < 1 || self.Persistence > 5 || self.AerialPreference < 1 || self.AerialPreference > 5 || self.RepositionSkill < 1 || self.RepositionSkill > 5)
        {
            self.Terminate("failure", "invalid_behavior_profile");
            return;
        }
        self._runStart = Time.GameTime;
        self._terminationReason = "none";
        self._spawnLatched = false;
        self._orderSequence = PersistentData.GetProperty("AICadetsCmdSequence", 0);
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
            if (self._spawnLatched)
            {
                self.Terminate("failure", "spawn_latched_but_waiting");
                return;
            }
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
        if (Game.IsEnding)
        {
            self.Terminate("safe_termination", "game_ending");
            return;
        }
        self.ReadOrders();
        if (Time.GameTime >= self._nextOrderStatus)
        {
            self._nextOrderStatus = Time.GameTime + 1.0;
            self.PublishOrderStatus();
        }
        if (self._state == "Hold")
        {
            return;
        }
        if (self.IsSupplyState())
        {
            if (self._cadet.CurrentGas > self._supplyGasBefore + 5.0)
            {
                self.CompleteResupply("gas_increase_verified");
                return;
            }
        }
        if (!self.IsSupplyState() && self._cadet.CurrentGas <= self.ResupplyTriggerGas)
        {
            self.BeginResupply("low_gas");
            return;
        }
        if (Time.GameTime >= self._nextTickReport)
        {
            self._nextTickReport = Time.GameTime + 5.0;
            self.LogEvent("mission_snapshot", "gas=" + Convert.ToString(self._cadet.CurrentGas) + " position=" + Convert.ToString(self._cadet.Position) + " speed=" + Convert.ToString(self._cadet.Velocity.Magnitude) + " ai_state=" + self._cadet.GetAIState() + " titans=" + Convert.ToString(Game.Titans.Count) + " humans=" + Convert.ToString(Game.Humans.Count) + " player_humans=" + Convert.ToString(Game.PlayerHumans.Count));
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

        if (self._state == "SeekSupply")
        {
            self.SeekSupplyStep();
            return;
        }
        if (self._state == "AtSupply")
        {
            self.AtSupplyStep();
            return;
        }
        if (self._state == "ExploreSupply")
        {
            self.ExploreSupplyStep();
            return;
        }
        if (self._state == "ExploreGround")
        {
            self.ExploreGroundStep();
            return;
        }
        if (self._state == "RecoverGround")
        {
            self.RecoverGroundStep();
            return;
        }
        if (self._state == "ApproachGround")
        {
            self.ApproachGroundStep();
            return;
        }
        if (self._state == "Explore")
        {
            self.ExploreStep();
            return;
        }
        if (self._state == "Regroup")
        {
            if (Time.GameTime - self._stateStart >= 0.35 && Time.GameTime >= self._noTargetCooldownUntil)
            {
                if (self._orderMode == "Explore")
                {
                    self.Enter("Explore", "regroup_explore");
                }
                else
                {
                    self.Enter("AcquireTarget", "regroup_complete");
                }
            }
            return;
        }
        if (self._state == "AcquireTarget")
        {
            if (self._orderMode == "Explore")
            {
                self.Enter("Explore", "manual_patrol");
                return;
            }
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
                self._targetDamageByCadet = true;
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
                self._targetKillByCadet = byCadet;
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
        if (self.HookReach < 20.0 || self.HookReach > 70.0 || self.AnchorRise < 4.0 || self.AnchorRise > 25.0 || self.BurstSeconds < 0.1 || self.BurstSeconds > 0.8 || self.MinGasReserve < 4.0 || self.MinAttackGas <= self.MinGasReserve || self.AttackRange < 6.0 || self.AttackRange > 18.0 || self.MaxTraversePerTarget < 1 || self.MaxTraversePerTarget > 40 || self.MaxTargetRetries < 1 || self.MaxTargetRetries > 6 || self.MaxRecoveriesPerTarget < 0 || self.MaxRecoveriesPerTarget > 4 || self.ResupplyTriggerGas <= self.MinAttackGas || self.ResupplyTriggerGas > 100.0 || self.SupplyArrivalRange < 1.0 || self.SupplyArrivalRange > 12.0 || self.SupplySearchTimeout < 20.0 || self.SupplySearchTimeout > 180.0)
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
        # Latch spawn independently of operational state. In the old
        # implementation an interrupted spawn could permanently strand the
        # controller in Done, suppressing all future orders.
        self._spawnLatched = true;
        self.Enter("Spawning", "spawn_latched");
        self._cadet = Game.SpawnHumanAt(1, "Levi", LoadoutEnum.HumanBlades, spawnPos, 0.0);
        if (self._cadet == null || !self._cadet.IsMine || !self._cadet.IsAlive)
        {
            self.Terminate("failure", "spawn_failed_or_not_owned");
            return;
        }
        self._cadet.Name = self._cadetName;
        PersistentData.SetProperty("AICadetsM2TerminalReason-" + self._cadetName, "none");
        PersistentData.SetProperty("AICadetsM2TerminalTime-" + self._cadetName, 0.0);
        PersistentData.SetProperty("AICadetsM2RunId-" + self._cadetName, self._runId);
        self._cadet.SetDisplayName(self._cadetName, true);
        self._cadet.Idle();
        self._direction = Vector3.Normalize(Vector3(host.Forward.X, 0.0, host.Forward.Z));
        self.LogEvent("behavior_profile", "name=" + self.ProfileName + " persistence=" + Convert.ToString(self.Persistence) + " aerial=" + Convert.ToString(self.AerialPreference) + " reposition_skill=" + Convert.ToString(self.RepositionSkill));
        self.LogEvent("cadet_spawned", "name=" + self._cadetName + " view_id=" + Convert.ToString(self._cadet.ViewID));
        self.Enter("Regroup", "spawned");
        self.PublishOrderStatus();
        # Orders sent during WaitHost must not silently disappear.
        self.ReadOrders();
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
        self._targetDamageByCadet = false;
        self._targetKilled = false;
        self._targetKillByCadet = false;
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
            # Momentum breaks close choices only at acquisition, never every tick.
            if (self._cadet.Velocity.Magnitude >= 9.0)
            {
                score = score + Vector3.Dot(Vector3.Normalize(self._cadet.Velocity), Vector3.Normalize(toNape)) * 18.0;
            }
            if (self.MapHit(self._cadet.Position + Vector3(0.0, 1.0, 0.0), titan.NapePosition) != null)
            {
                score = score - 20.0;
            }
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
            self._noTargetCooldownUntil = Time.GameTime + self.ExploreScanSeconds;
            self._exploreNextScan = self._noTargetCooldownUntil;
            if (self._orderMode == "Engage")
            {
                self.Enter("Explore", "no_target_start_patrol");
            }
            else
            {
                self.Enter("Explore", "explore_order");
            }
            return;
        }
        self._noTargetCooldownUntil = 0.0;
        self._cadet.Idle();
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
        if (self._lastDistanceToNape > self.GroundApproachThreshold && self._cadet.Grounded)
        {
            self.StartGroundApproach(false);
            return;
        }
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
        self._cadet.Idle();
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
        self.FindTraverseAnchor();
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

    # Shared geometric probe. It never cancels navigation or launches a hook.
    function FindTraverseAnchor()
    {
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
    }

    function HasTravelAnchor(goal)
    {
        oldAnchor = self._anchor;
        oldDirection = self._direction;
        oldLeg = self._trLeg;
        toGoal = goal - self._cadet.Position;
        self._direction = Vector3.Normalize(Vector3(toGoal.X, 0.0, toGoal.Z));
        self._trLeg = 1;
        self.FindTraverseAnchor();
        found = self._anchor != null;
        self._anchor = oldAnchor;
        self._direction = oldDirection;
        self._trLeg = oldLeg;
        return found;
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
        if (self._traverseMode == "supply")
        {
            self.LogEvent("supply_traverse_end", "outcome=" + self._trOutcome + " position=" + Convert.ToString(self._cadet.Position));
            self.Enter("SeekSupply", "supply_flight_complete");
            return;
        }
        if (self._traverseMode == "approach" && self._trOutcome == "no_suitable_anchor" && self._cadet.Grounded)
        {
            self.StartGroundApproach(true);
            return;
        }
        if (self._traverseMode == "explore")
        {
            distance = Vector3.Distance(self._cadet.Position, self._trStartPosition);
            self.LogEvent("explore_traverse_end", "outcome=" + self._trOutcome + " distance=" + Convert.ToString(distance) + " pattern=" + Convert.ToString(self._exploreIndex));
            if (distance < self.TraverseProgressMin)
            {
                self._exploreFailures = self._exploreFailures + 1;
            }
            else
            {
                self._exploreFailures = 0;
            }
            self._exploreNextAction = Time.GameTime + 0.75;
            self.Enter("Explore", "patrol_step_finished");
            return;
        }
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
            self._banUntil = Time.GameTime + 15.0;
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
        self._targetDamaged = false;
        self._targetDamageByCadet = false;
        self._targetKilled = false;
        self._targetKillByCadet = false;
        self._cadet.AimAt(self._target.NapePosition);
        self._cadet.Attack(true);
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
        if (self._targetKilled)
        {
            self.LogEvent("attack_result", "confirmed_kill=true by_cadet=" + Convert.ToString(self._targetKillByCadet) + " target=" + Convert.ToString(self._targetViewId));
            self.Enter("AcquireTarget", "target_killed");
            return;
        }
        if (!self.RefreshTarget())
        {
            self.LogEvent("attack_result", "confirmed_kill=false reason=target_lost target=" + Convert.ToString(self._targetViewId));
            self.Enter("AcquireTarget", "target_lost_after_attack");
            return;
        }
        if (self._targetDamaged)
        {
            self.LogEvent("attack_result", "confirmed_damage=true by_cadet=" + Convert.ToString(self._targetDamageByCadet) + " target=" + Convert.ToString(self._targetViewId));
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

    function RecoveryBudget()
    {
        budget = 1.0 + (self.Persistence - 1.0) * 0.5;
        if (budget > self.MaxRecoveriesPerTarget)
        {
            budget = self.MaxRecoveriesPerTarget;
        }
        return budget;
    }

    function RecoverGroundStep()
    {
        if (!self.RefreshTarget())
        {
            self._cadet.Idle();
            self.Enter("AcquireTarget", "reposition_target_lost");
            return;
        }
        if (Vector3.Distance(self._cadet.Position, self._groundGoal) <= 4.0 || Time.GameTime - self._stateStart >= 6.0)
        {
            self._cadet.Idle();
            self.LogEvent("reposition_end", "moved=" + Convert.ToString(Vector3.Distance(self._cadet.Position, self._groundStartPosition)));
            self.Enter("PlanApproach", "reposition_retry_same_target");
        }
    }

    function RecoverStep()
    {
        if (self._targetRecoveries >= self.RecoveryBudget())
        {
            self.LogEvent("recover_exhausted", "target=" + Convert.ToString(self._targetViewId) + " reason=" + self._lastFailureReason);
            self._bannedTargetViewId = self._targetViewId;
            self._banUntil = Time.GameTime + 15.0;
            self.Enter("AcquireTarget", "recover_budget_exhausted");
            return;
        }
        if (self._cadet.Grounded && self.RefreshTarget())
        {
            self._targetRecoveries = self._targetRecoveries + 1;
            toTarget = self._target.Position - self._cadet.Position;
            direction = Vector3.Normalize(Vector3(toTarget.X, 0.0, toTarget.Z));
            right = Vector3(direction.Z, 0.0, 0.0 - direction.X);
            if (self._targetRecoveries == 2)
            {
                right = right * -1.0;
            }
            self._groundGoal = self._cadet.Position + direction * 8.0 + right * (8.0 + self.RepositionSkill * 3.0);
            if (self.MapHit(self._cadet.Position + Vector3(0.0, 1.0, 0.0), self._groundGoal + Vector3(0.0, 1.0, 0.0)) != null)
            {
                self._groundGoal = self._cadet.Position + direction * 8.0 - right * (8.0 + self.RepositionSkill * 3.0);
            }
            self.StopODM();
            self._groundStartPosition = self._cadet.Position;
            self._cadet.MoveTo(self._groundGoal, 3.0);
            self.LogEvent("reposition_start", "goal=" + Convert.ToString(self._groundGoal) + " attempt=" + Convert.ToString(self._targetRecoveries));
            self.Enter("RecoverGround", "retain_target_change_route");
            return;
        }
        if (!self._cadet.LeftHookReady || self._cadet.CurrentGas < self.MinAttackGas)
        {
            self._bannedTargetViewId = self._targetViewId;
            self._banUntil = Time.GameTime + 15.0;
            self._target = null;
            self._targetViewId = 0;
            self._exploreFailures = 3;
            self._exploreNextAction = 0.0;
            self._exploreNextScan = Time.GameTime + self.ExploreScanSeconds;
            self.Enter("Explore", "recovery_unavailable_patrol");
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

    # Lightweight maneuver-policy dispatcher: currently four bounded patterns.
    # Routes are actual heading/rise choices, not cosmetic animations. Each
    # pattern can later be moved into its own named skill implementation.
    function ChooseExploreHeading()
    {
        baseDir = Vector3(self._cadet.Forward.X, 0.0, self._cadet.Forward.Z);
        if (baseDir.Magnitude < 0.1)
        {
            baseDir = Vector3(0.0, 0.0, 1.0);
        }
        baseDir = baseDir.Normalized;
        right = Vector3(baseDir.Z, 0.0, 0.0 - baseDir.X);
        pattern = self._exploreIndex;
        if (pattern == 0)
        {
            return Vector3.Normalize(baseDir + right * 0.4);
        }
        if (pattern == 1)
        {
            return Vector3.Normalize(baseDir - right * 0.7);
        }
        if (pattern == 2)
        {
            return Vector3.Normalize(baseDir + right * 0.85);
        }
        return Vector3.Normalize(baseDir - right * 0.35);
    }

    function ExploreStep()
    {
        if (self._orderMode == "Engage" && Time.GameTime >= self._exploreNextScan)
        {
            self._exploreNextScan = Time.GameTime + self.ExploreScanSeconds;
            self.AcquireTarget();
            if (self._target != null)
            {
                return;
            }
        }
        if (Time.GameTime < self._exploreNextAction)
        {
            return;
        }
        if (self._cadet.Velocity.Magnitude > 9.0 && !self._cadet.Grounded)
        {
            # Avoid overriding a coasting maneuver with a new initial jump.
            self._exploreNextAction = Time.GameTime + 0.5;
            return;
        }
        self._exploreIndex = self._exploreIndex + 1;
        if (self._exploreIndex >= 4)
        {
            self._exploreIndex = 0;
        }
        self._exploreDirection = self.ChooseExploreHeading();
        self._exploreStartPosition = self._cadet.Position;
        exploreGoal = self._cadet.Position + self._exploreDirection * self.ExploreSegmentDistance + Vector3(0.0, self.AnchorRise, 0.0);
        self.LogEvent("explore_step", "pattern=" + Convert.ToString(self._exploreIndex) + " goal=" + Convert.ToString(exploreGoal) + " failures=" + Convert.ToString(self._exploreFailures));
        if (self._cadet.LeftHookReady && self._cadet.CurrentGas > self.MinAttackGas && self._exploreFailures < 3)
        {
            self.StartTraverse(exploreGoal, "explore");
            return;
        }
        self.ExploreGroundMove();
    }

    # Human.Move is a documented ordinary controller action; use it only when
    # grounded and a short forward map probe does not report a wall.
    # Ground navigation uses engine's persistent AI MoveTo state. Do not
    # invoke Idle or a new hook search until the route completes or times out.
    function StartGroundApproach(fallback)
    {
        if (!self.RefreshTarget())
        {
            self.Enter("AcquireTarget", "ground_target_lost");
            return;
        }
        self._groundFallback = fallback;
        toTarget = self._target.Position - self._cadet.Position;
        self._groundBearing = Vector3.Normalize(Vector3(toTarget.X, 0.0, toTarget.Z));
        self._nextTravelProbe = Time.GameTime + 1.0;
        self._groundMovementStartedAt = Time.GameTime;
        self._groundProgressPosition = self._cadet.Position;
        self._groundNextCheck = Time.GameTime + self.GroundProgressWindow;
        self._groundStalledChecks = 0;
        stopRange = 24.0;
        if (fallback)
        {
            stopRange = 4.0;
        }
        if (self.GroundSteering == "Direct")
        {
            self._cadet.Idle();
        }
        else
        {
            self._cadet.MoveToTarget(self._target, stopRange);
        }
        self.Enter("ApproachGround", "navigate_to_titan");
        self.LogEvent("motion_command", "kind=ground_target driver=" + self.GroundSteering + " fallback=" + Convert.ToString(fallback) + " range=" + Convert.ToString(stopRange) + " view_id=" + Convert.ToString(self._targetViewId) + " ai_state=" + self._cadet.GetAIState());
    }

    function ApproachGroundStep()
    {
        if (!self.RefreshTarget())
        {
            self._cadet.Idle();
            self.Enter("AcquireTarget", "ground_target_invalid");
            return;
        }
        distance = Vector3.Distance(self._cadet.Position, self._target.NapePosition);
        if ((!self._groundFallback && distance <= self.GroundApproachThreshold) || (self._groundFallback && (distance <= self.AttackRange || Time.GameTime - self._groundMovementStartedAt >= self.GroundProgressWindow * 3.0)))
        {
            self._cadet.Idle();
            self.LogEvent("motion_segment_done", "kind=ground_target fallback=" + Convert.ToString(self._groundFallback) + " distance=" + Convert.ToString(distance));
            self.Enter("PlanApproach", "ground_approach_close");
            return;
        }
        if (Time.GameTime >= self._nextTravelProbe)
        {
            self._nextTravelProbe = Time.GameTime + 14.0 - self.AerialPreference * 2.0;
            if (self._cadet.LeftHookReady && self._cadet.CurrentGas > self.MinAttackGas && self._targetTraverseCount < self.MaxTraversePerTarget)
            {
                viable = self.HasTravelAnchor(self._target.NapePosition);
                self.LogEvent("travel_probe", "viable=" + Convert.ToString(viable) + " distance=" + Convert.ToString(distance));
                if (viable)
                {
                    self.StartTraverse(self._target.NapePosition, "approach");
                    return;
                }
            }
        }
        if (self.GroundSteering == "Direct")
        {
            if (!self._cadet.Grounded)
            {
                self._cadet.Idle();
                return;
            }
            toTarget = self._target.Position - self._cadet.Position;
            direction = Vector3.Normalize(Vector3(toTarget.X, 0.0, toTarget.Z));
            start = self._cadet.Position + Vector3(0.0, 1.0, 0.0);
            # A bounded diagnostic alternate, not a replacement navmesh planner.
            if (Vector3.Distance(self._cadet.Position, self._target.Position) <= 4.0 || self.MapHit(start, start + direction * 6.0) != null)
            {
                self._cadet.Idle();
                self._lastFailureReason = "direct_route_blocked_or_near";
                self.Enter("Recover", "direct_route_blocked_or_near");
                return;
            }
            self._cadet.Move(direction);
        }
        if (Time.GameTime >= self._groundNextCheck)
        {
            progress = Vector3.Distance(self._cadet.Position, self._groundProgressPosition);
            forwardProgress = Vector3.Dot(self._cadet.Position - self._groundProgressPosition, self._groundBearing);
            self.LogEvent("pursuit_progress", "toward_previous_target=" + Convert.ToString(forwardProgress) + " displacement=" + Convert.ToString(progress) + " distance=" + Convert.ToString(distance));
            toTarget = self._target.Position - self._cadet.Position;
            self._groundBearing = Vector3.Normalize(Vector3(toTarget.X, 0.0, toTarget.Z));
            self.LogEvent("motion_observed", "kind=ground_target moved=" + Convert.ToString(progress) + " speed=" + Convert.ToString(self._cadet.Velocity.Magnitude) + " ai_state=" + self._cadet.GetAIState());
            self._groundProgressPosition = self._cadet.Position;
            self._groundNextCheck = Time.GameTime + self.GroundProgressWindow;
            if (progress < 1.0 || forwardProgress < 1.0)
            {
                self._groundStalledChecks = self._groundStalledChecks + 1;
            }
            else
            {
                self._groundStalledChecks = 0;
            }
            if (self._groundStalledChecks >= 2)
            {
                self.LogEvent("motion_stalled", "kind=ground_target dist=" + Convert.ToString(distance));
                self._cadet.Idle();
                if (self._targetRecoveries < self.RecoveryBudget())
                {
                    self._lastFailureReason = "ground_not_advancing";
                    self.Enter("Recover", "ground_not_advancing");
                    return;
                }
                self._bannedTargetViewId = self._targetViewId;
                self._banUntil = Time.GameTime + 15.0;
                self.LogEvent("target_banned", "view_id=" + Convert.ToString(self._targetViewId) + " reason=ground_stalled");
                self._target = null;
                self._targetViewId = 0;
                self._exploreNextScan = Time.GameTime + self.ExploreScanSeconds;
                self._exploreNextAction = 0.0;
                self._exploreFailures = 3;
                self.Enter("Explore", "ground_approach_stalled");
            }
        }
    }

    function ExploreGroundMove()
    {
        direction = self._exploreDirection;
        start = self._cadet.Position + Vector3(0.0, 1.0, 0.0);
        ahead = start + direction * 4.0;
        if (self.MapHit(start, ahead) != null)
        {
            self._exploreIndex = self._exploreIndex + 1;
            if (self._exploreIndex >= 4)
            {
                self._exploreIndex = 0;
            }
            direction = self.ChooseExploreHeading();
        }
        self._groundGoal = self._cadet.Position + direction * self.ExploreSegmentDistance;
        self._groundStartPosition = self._cadet.Position;
        self._groundProgressPosition = self._cadet.Position;
        self._groundMovementStartedAt = Time.GameTime;
        self._groundNextCheck = Time.GameTime + self.GroundProgressWindow;
        self._groundStalledChecks = 0;
        self._cadet.MoveTo(self._groundGoal, 4.0);
        self.Enter("ExploreGround", "persistent_ground_patrol");
        self.LogEvent("motion_command", "kind=ground_explore goal=" + Convert.ToString(self._groundGoal) + " ai_state=" + self._cadet.GetAIState());
    }

    function ExploreGroundStep()
    {
        if (self._orderMode == "Engage" && Time.GameTime >= self._exploreNextScan)
        {
            self._exploreNextScan = Time.GameTime + self.ExploreScanSeconds;
            self.AcquireTarget();
            if (self._target != null)
            {
                return;
            }
            self.Enter("ExploreGround", "patrol_while_scanning");
        }
        if (Vector3.Distance(self._cadet.Position, self._groundGoal) <= 5.0 || Time.GameTime - self._groundMovementStartedAt >= self.ExploreGroundSeconds)
        {
            moved = Vector3.Distance(self._cadet.Position, self._groundStartPosition);
            self.LogEvent("motion_segment_done", "kind=ground_explore moved=" + Convert.ToString(moved));
            self._cadet.Idle();
            self._exploreFailures = 0;
            self._exploreNextAction = Time.GameTime + 0.1;
            self.Enter("Explore", "ground_patrol_finished");
            return;
        }
        if (Time.GameTime >= self._groundNextCheck)
        {
            moved = Vector3.Distance(self._cadet.Position, self._groundProgressPosition);
            self.LogEvent("motion_observed", "kind=ground_explore moved=" + Convert.ToString(moved) + " speed=" + Convert.ToString(self._cadet.Velocity.Magnitude) + " ai_state=" + self._cadet.GetAIState());
            self._groundProgressPosition = self._cadet.Position;
            self._groundNextCheck = Time.GameTime + self.GroundProgressWindow;
            if (moved < 1.0)
            {
                self._groundStalledChecks = self._groundStalledChecks + 1;
                self.LogEvent("motion_stalled", "kind=ground_explore check=" + Convert.ToString(self._groundStalledChecks));
            }
        }
    }

    # Shared master-owned, local-only command channel. The UI addon increments
    # the sequence when the user presses Engage / Explore / Hold for All or one
    # named bot. The command is never persisted to disk by this feature.
    # The command panel writes a request. Only this owned movement controller
    # can acknowledge it as accepted, AFTER changing its own operational state.
    # No ack means no active M2 controller received the message.
    function AcknowledgeOrder(sequence, order)
    {
        key = self._cadetName;
        self._lastAppliedOrderSequence = sequence;
        PersistentData.SetProperty("AICadetsM2AckSeq-" + key, sequence);
        PersistentData.SetProperty("AICadetsM2AckState-" + key, self._state);
        PersistentData.SetProperty("AICadetsM2AckMode-" + key, order);
        self.LogEvent("order_applied", "seq=" + Convert.ToString(sequence) + " mode=" + order + " state=" + self._state);
        self.PublishOrderStatus();
    }

    function PublishOrderStatus()
    {
        if (self._cadet == null || !self._cadet.IsMine || self._cadetName == "")
        {
            return;
        }
        key = self._cadetName;
        PersistentData.SetProperty("AICadetsM2Build-" + key, self._buildTag);
        PersistentData.SetProperty("AICadetsM2Profile-" + key, self.ProfileName + " P=" + Convert.ToString(self.Persistence) + " A=" + Convert.ToString(self.AerialPreference) + " R=" + Convert.ToString(self.RepositionSkill) + " ground=" + self.GroundSteering);
        PersistentData.SetProperty("AICadetsM2Heartbeat-" + key, Time.GameTime);
        PersistentData.SetProperty("AICadetsM2State-" + key, self._state);
        PersistentData.SetProperty("AICadetsM2Mode-" + key, self._orderMode);
        PersistentData.SetProperty("AICadetsM2RunId-" + key, self._runId);
        PersistentData.SetProperty("AICadetsM2StatusTime-" + key, Time.GameTime);
        PersistentData.SetProperty("AICadetsM2TargetId-" + key, self._targetViewId);
        targetInfo = "none";
        if (self._target != null && self._target.IsAlive)
        {
            targetInfo = "pos=" + Convert.ToString(self._target.Position) + " nape=" + Convert.ToString(self._target.NapePosition) + " distance=" + Convert.ToString(Vector3.Distance(self._cadet.Position, self._target.NapePosition));
        }
        PersistentData.SetProperty("AICadetsM2TargetInfo-" + key, targetInfo);
        groundGoal = "none";
        traverseGoal = "none";
        if (self._groundGoal != null)
        {
            groundGoal = Convert.ToString(self._groundGoal);
        }
        if (self._traverseGoal != null)
        {
            traverseGoal = Convert.ToString(self._traverseGoal);
        }
        PersistentData.SetProperty("AICadetsM2Navigation-" + key, "ground_goal=" + groundGoal + " fallback=" + Convert.ToString(self._groundFallback) + " traverse=" + self._traverseMode + " traverse_goal=" + traverseGoal + " order_seq=" + Convert.ToString(self._lastAppliedOrderSequence));
    }

    function ReadOrders()
    {
        sequence = PersistentData.GetProperty("AICadetsCmdSequence", 0);
        if (sequence == self._orderSequence)
        {
            return;
        }
        self._orderSequence = sequence;
        scope = PersistentData.GetProperty("AICadetsCmdScope", "all");
        if (scope != "all" && scope != self._cadetName)
        {
            self.LogEvent("order_ignored", "seq=" + Convert.ToString(sequence) + " scope=" + scope);
            return;
        }
        order = PersistentData.GetProperty("AICadetsCmdMode", "Engage");
        if (order != "Engage" && order != "Explore" && order != "Hold" && order != "Resupply" && order != "GroundEngine" && order != "GroundDirect")
        {
            self.LogEvent("order_rejected", "seq=" + Convert.ToString(sequence) + " mode=" + order);
            return;
        }
        if (order == "GroundEngine" || order == "GroundDirect")
        {
            self.GroundSteering = "Engine";
            if (order == "GroundDirect")
            {
                self.GroundSteering = "Direct";
            }
            if (self._state == "ApproachGround")
            {
                self.StartGroundApproach(self._groundFallback);
            }
            self.LogEvent("ground_driver_changed", "driver=" + self.GroundSteering);
            self.AcknowledgeOrder(sequence, order);
            return;
        }
        previousMode = self._orderMode;
        self.StopODM();
        self._cadet.Idle();
        self.LogEvent("order_received", "seq=" + Convert.ToString(sequence) + " mode=" + order + " scope=" + scope);

        if (order == "Resupply")
        {
            if (self.IsSupplyState())
            {
                self._orderMode = "Resupply";
                self.LogEvent("resupply_already_in_progress", "gas=" + Convert.ToString(self._cadet.CurrentGas));
                self.AcknowledgeOrder(sequence, order);
                return;
            }
            if (previousMode == "Explore")
            {
                self._resumeAfterSupply = "Explore";
            }
            else
            {
                self._resumeAfterSupply = "Engage";
            }
            self._orderMode = "Resupply";
            self.BeginResupply("manual_order");
            self.AcknowledgeOrder(sequence, order);
            return;
        }

        if (self.IsSupplyState())
        {
            self._cadet.AutoRefillGas = self._supplyAutoRefillBefore;
        }
        self._orderMode = order;
        if (order == "Hold")
        {
            self.Enter("Hold", "user_hold");
            self.AcknowledgeOrder(sequence, order);
            return;
        }
        if (order == "Explore")
        {
            self._target = null;
            self._targetViewId = 0;
            self._exploreNextAction = 0.0;
            self._exploreNextScan = Time.GameTime + self.ExploreScanSeconds;
            self.Enter("Explore", "user_explore");
            self.AcknowledgeOrder(sequence, order);
            return;
        }
        self.Enter("AcquireTarget", "user_engage");
        self.AcknowledgeOrder(sequence, order);
    }

    function IsSupplyState()
    {
        return self._state == "SeekSupply" || self._state == "AtSupply" || self._state == "ExploreSupply" || (self.IsTraverseState() && self._traverseMode == "supply");
    }

    # Only actual station interactions can grant gas. Never write CurrentGas
    # or call RefillImmediate. Set AutoRefillGas while seeking: the documented
    # SupplyStation collider determines when an owned human can replenish.
    function BeginResupply(reason)
    {
        if (self.IsSupplyState())
        {
            return;
        }
        if (self._orderMode != "Resupply")
        {
            self._resumeAfterSupply = self._orderMode;
        }
        self.StopODM();
        self._cadet.Idle();
        self._supplyGasBefore = self._cadet.CurrentGas;
        self._supplySearchStarted = Time.GameTime;
        self._supplyArrivalStarted = 0.0;
        self._supplyScanDue = 0.0;
        self._supplyMoveDue = 0.0;
        self._supplyLastProgressAt = Time.GameTime;
        self._supplyLastPosition = self._cadet.Position;
        self._supplyWaypoint = null;
        self._supplyDetour = 0;
        self._supplyPoint = null;
        self._supplySource = "none";
        self._supplyAutoRefillBefore = self._cadet.AutoRefillGas;
        self._cadet.AutoRefillGas = true;
        self.LogEvent("resupply_requested", "reason=" + reason + " gas=" + Convert.ToString(self._supplyGasBefore));
        self.Enter("SeekSupply", reason);
    }

    function FindNearestSupply()
    {
        best = 10000000.0;
        self._supplyPoint = null;
        self._supplySource = "none";
        # Official components can be enumerated in Custom Logic maps. Built-in
        # City scene supply objects may not be MapObjects; use host-mark fallback.
        for (station in Map.FindMapObjectsByComponent("SupplyStation"))
        {
            if (station != null)
            {
                distance = Vector3.Distance(self._cadet.Position, station.Position);
                if (distance < best)
                {
                    best = distance;
                    self._supplyPoint = station.Position;
                    self._supplySource = "map_component";
                }
            }
        }
        version = PersistentData.GetProperty("AICadetsSupplyRevision", 0);
        if (version > 0)
        {
            point = Vector3(PersistentData.GetProperty("AICadetsSupplyX", 0.0), PersistentData.GetProperty("AICadetsSupplyY", 0.0), PersistentData.GetProperty("AICadetsSupplyZ", 0.0));
            distance = Vector3.Distance(self._cadet.Position, point);
            if (distance < best)
            {
                best = distance;
                self._supplyPoint = point;
                self._supplySource = "host_marked_unverified";
            }
        }
        if (self._supplyPoint != null)
        {
            self.LogEvent("supply_selected", "source=" + self._supplySource + " distance=" + Convert.ToString(best) + " point=" + Convert.ToString(self._supplyPoint));
        }
        else
        {
            self.LogEvent("supply_not_visible", "source=no_map_component_or_host_marker");
        }
    }

    # Progress-checked navigation: prefer documented AI ground MoveTo, use
    # nearby linecasts to select a finite lateral detour when stuck, and
    # preserve ODM as an airborne fallback if adequate gas remains.
    function SeekSupplyStep()
    {
        if (Time.GameTime - self._supplySearchStarted > self.SupplySearchTimeout)
        {
            self.LogEvent("resupply_failed", "reason=search_timeout gas=" + Convert.ToString(self._cadet.CurrentGas));
            self._cadet.AutoRefillGas = self._supplyAutoRefillBefore;
            self.StopODM();
            self._cadet.Idle();
            self.Enter("Hold", "supply_search_timeout");
            return;
        }
        if (self._supplyPoint == null)
        {
            self.FindNearestSupply();
            if (self._supplyPoint == null)
            {
                self._exploreNextAction = 0.0;
                self.Enter("ExploreSupply", "no_registered_station");
                return;
            }
        }
        distance = Vector3.Distance(self._cadet.Position, self._supplyPoint);
        if (distance <= self.SupplyArrivalRange)
        {
            self.StopODM();
            self._cadet.Idle();
            self._supplyArrivalStarted = Time.GameTime;
            self.LogEvent("supply_arrived", "source=" + self._supplySource + " gas=" + Convert.ToString(self._cadet.CurrentGas));
            self.Enter("AtSupply", "within_supply_radius");
            return;
        }
        if (Vector3.Distance(self._cadet.Position, self._supplyLastPosition) >= 3.0)
        {
            self._supplyLastPosition = self._cadet.Position;
            self._supplyLastProgressAt = Time.GameTime;
            self._supplyWaypoint = null;
        }
        if (Time.GameTime - self._supplyLastProgressAt >= 8.0)
        {
            self._supplyLastProgressAt = Time.GameTime;
            self._supplyDetour = self._supplyDetour + 1;
            toStation = self._supplyPoint - self._cadet.Position;
            flat = Vector3(toStation.X, 0.0, toStation.Z);
            if (flat.Magnitude >= 1.0)
            {
                direction = flat.Normalized;
                right = Vector3(direction.Z, 0.0, 0.0 - direction.X);
                if (self._supplyDetour == 1)
                {
                    self._supplyWaypoint = self._cadet.Position + direction * 12.0 + right * 18.0;
                }
                else
                {
                    self._supplyWaypoint = self._cadet.Position + direction * 12.0 - right * 18.0;
                    self._supplyDetour = 0;
                }
                self.LogEvent("supply_detour", "waypoint=" + Convert.ToString(self._supplyWaypoint));
            }
        }
        if (Time.GameTime >= self._supplyMoveDue)
        {
            self._supplyMoveDue = Time.GameTime + 0.8;
            waypoint = self._supplyPoint;
            if (self._supplyWaypoint != null)
            {
                waypoint = self._supplyWaypoint;
                if (Vector3.Distance(self._cadet.Position, waypoint) <= 5.0)
                {
                    self._supplyWaypoint = null;
                    waypoint = self._supplyPoint;
                }
            }
            if (self._cadet.Grounded)
            {
                self._cadet.MoveTo(waypoint, self.SupplyArrivalRange);
                self.LogEvent("supply_ground_route", "remaining=" + Convert.ToString(distance) + " waypoint=" + Convert.ToString(waypoint));
            }
            if (!self._cadet.Grounded && self._cadet.CurrentGas > self.MinAttackGas + 4.0 && self._cadet.LeftHookReady)
            {
                self.StartTraverse(waypoint + Vector3(0.0, 6.0, 0.0), "supply");
            }
        }
    }

    function AtSupplyStep()
    {
        # Collision-based AutoRefillGas is active, but do not claim success
        # unless CurrentGas rises. This also detects a wrong host marker.
        if (Time.GameTime - self._supplyArrivalStarted >= self.SupplyRefillTimeout)
        {
            self.LogEvent("supply_not_refilling", "source=" + self._supplySource + " gas=" + Convert.ToString(self._cadet.CurrentGas));
            self._supplyPoint = null;
            self._exploreNextAction = 0.0;
            self.Enter("ExploreSupply", "station_inactive_or_unverified");
        }
    }

    function ExploreSupplyStep()
    {
        if (Time.GameTime - self._supplySearchStarted > self.SupplySearchTimeout)
        {
            self.LogEvent("resupply_failed", "reason=station_not_found gas=" + Convert.ToString(self._cadet.CurrentGas));
            self._cadet.AutoRefillGas = self._supplyAutoRefillBefore;
            self._cadet.Idle();
            self.Enter("Hold", "no_supply_available");
            return;
        }
        if (Time.GameTime >= self._supplyScanDue)
        {
            self._supplyScanDue = Time.GameTime + 6.0;
            self.FindNearestSupply();
            if (self._supplyPoint != null)
            {
                self.Enter("SeekSupply", "station_discovered");
                return;
            }
        }
        if (Time.GameTime >= self._exploreNextAction && self._cadet.Grounded)
        {
            self._exploreIndex = self._exploreIndex + 1;
            if (self._exploreIndex >= 4)
            {
                self._exploreIndex = 0;
            }
            self._exploreDirection = self.ChooseExploreHeading();
            waypoint = self._cadet.Position + self._exploreDirection * 35.0;
            self._cadet.MoveTo(waypoint, 4.0);
            self._exploreNextAction = Time.GameTime + 7.0;
            self.LogEvent("supply_search_patrol", "waypoint=" + Convert.ToString(waypoint) + " gas=" + Convert.ToString(self._cadet.CurrentGas));
        }
    }

    function CompleteResupply(reason)
    {
        self.LogEvent("resupply_verified", "reason=" + reason + " gas_before=" + Convert.ToString(self._supplyGasBefore) + " gas_after=" + Convert.ToString(self._cadet.CurrentGas));
        self._cadet.AutoRefillGas = self._supplyAutoRefillBefore;
        self._supplyPoint = null;
        self._cadet.Idle();
        if (self._resumeAfterSupply == "Explore")
        {
            self._orderMode = "Explore";
            self.Enter("Explore", "resupplied_resume_patrol");
        }
        else
        {
            self._orderMode = "Engage";
            self.Enter("AcquireTarget", "resupplied_resume_combat");
        }
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
        self._eventId = self._eventId + 1;
        line = "build=" + self._buildTag + " driver=" + self.GroundSteering + " id=" + Convert.ToString(self._eventId) + " mode=" + self._orderMode + " t=" + Convert.ToString(Time.GameTime) + " run=" + self._runId + " cadet=" + self._cadetName + " state=" + self._state + " target=" + Convert.ToString(self._targetViewId) + " event=" + event + " " + details;
        if (self._eventId <= 3000)
        {
            self._trace = self._trace + line + "\n";
            if (self.RecordDecisionTrace || self.SaveRunReport)
            {
                PersistentData.SetProperty("AICadetsM2Report-" + self._cadetName, self._trace);
            }
        }
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
        PersistentData.SetProperty("AICadetsM2Report-" + self._cadetName, self._trace);
        PersistentData.SaveToFile("AICadetsM2Report_" + self._runId, false);
    }

    function Terminate(resultClass, reason)
    {
        self.StopODM();
        if (Network.IsMasterClient && self._cadet != null && self._cadet.IsMine)
        {
            self._cadet.Idle();
        }
        if (self._state == "Done")
        {
            return;
        }
        if (self.IsSupplyState() && self._cadet != null && self._cadet.IsMine)
        {
            self._cadet.AutoRefillGas = self._supplyAutoRefillBefore;
        }
        self._terminationReason = reason;
        self.LogEvent("termination", "result_class=" + resultClass + " reason=" + reason + " kills_observed=" + Convert.ToString(self._killsObserved) + " titan_deaths_observed=" + Convert.ToString(self._titanDeathsObserved) + " damage_events=" + Convert.ToString(self._damageEvents));
        Game.Print("[AI Cadets M2] result_class=" + resultClass + " result_reason=" + reason + " run_id=" + self._runId + " cadet=" + self._cadetName + " target_retry=" + Convert.ToString(self._targetRetryCount) + " target_traverses=" + Convert.ToString(self._targetTraverseCount) + " target_recoveries=" + Convert.ToString(self._targetRecoveries) + " kills_observed=" + Convert.ToString(self._killsObserved) + " titan_deaths_observed=" + Convert.ToString(self._titanDeathsObserved));
        self.SaveReportIfEnabled();
        self.Enter("Done", "terminated");
        if (self._cadetName != "")
        {
            PersistentData.SetProperty("AICadetsM2TerminalReason-" + self._cadetName, reason);
            PersistentData.SetProperty("AICadetsM2TerminalTime-" + self._cadetName, Time.GameTime);
        }
        self.PublishOrderStatus();
    }
}
