# F8-toggle host-only command console for living M2 cadets.
# UI submissions are NOT acknowledgements; only the cadet controller writes
# AICadetsM2AckSeq-<bot name> after it accepts a command.
addon AICadetsCommandPanel
{
    Description = "F8 tactical orders plus a one-click, host-only M2 Direct / Hold / Direct capture sequence.";
    ToggleKey = "CustomKey/F8";
    RecoveryKey = "CustomKey/F9";
    MenuMaxSeconds = 45.0;
    _openedAt = 0.0;
    _initialized = false;
    _open = false;
    _panel = null;
    _actions = null;
    _selected = "all";
    _selectedLabel = null;
    _rosterLabel = null;
    _responseLabel = null;
    _seq = 0;
    _pendingSeq = 0;
    _reportedAckSeq = 0;
    _pendingMode = "none";
    _pendingScope = "all";
    _nextRefresh = 0.0;
    _supplyRevision = 0;
    _autoHoldTestStage = "idle";
    _autoHoldTestStarted = false;
    _autoHoldTestInternalDispatch = false;
    _autoHoldTestBot = "AICadetsM2-1";
    _autoHoldTestSequence = 0;
    _autoHoldTestDeadline = 0.0;
    _autoHoldTestGroundSince = -1.0;
    _autoHoldTestGroundPathStart = -1.0;
    _autoHoldTestHoldSince = -1.0;
    _autoHoldTestHoldPathStart = -1.0;
    _autoHoldTestResumeGroundSince = -1.0;
    _autoHoldTestResumePathStart = -1.0;
    _autoHoldTestTargetId = 0;
    _autoHoldTestHoldMotionWithin2 = false;
    _autoHoldTestTrace = "";

    function OnGameStart()
    {
        if (self._initialized || !Network.IsMasterClient)
        {
            return;
        }
        self._initialized = true;
        self._autoHoldTestStage = "idle";
        self._autoHoldTestStarted = false;
        self._autoHoldTestInternalDispatch = false;
        self._autoHoldTestSequence = 0;
        self._autoHoldTestDeadline = 0.0;
        self._autoHoldTestGroundSince = -1.0;
        self._autoHoldTestGroundPathStart = -1.0;
        self._autoHoldTestHoldSince = -1.0;
        self._autoHoldTestHoldPathStart = -1.0;
        self._autoHoldTestResumeGroundSince = -1.0;
        self._autoHoldTestResumePathStart = -1.0;
        self._autoHoldTestTargetId = 0;
        self._autoHoldTestHoldMotionWithin2 = false;
        self._autoHoldTestTrace = "";
        PersistentData.SetProperty("AICadetsM2AutoHoldTestTrace", self._autoHoldTestTrace);
        # Recover any global key/camera flags left over by the previous
        # input-disabling F8 panel. Never disable those flags when opening.
        self.RestoreHumanControls();
        self._seq = PersistentData.GetProperty("AICadetsCmdSequence", 0);
        self._supplyRevision = PersistentData.GetProperty("AICadetsSupplyRevision", 0);
        root = UI.GetRootVisualElement();
        # Top-left, hidden until F8; scrollable to fit 720p and avoid minimap.
        self._panel = UI.VisualElement().Absolute(true).Left(20).Top(72).Width(268).Padding(8).Active(false);
        self._panel.Add(UI.Label("AI Cadets | F8 close | F9 recover"));
        self._selectedLabel = UI.Label("Recipient: ALL M2 cadets");
        self._panel.Add(self._selectedLabel);
        self._rosterLabel = UI.Label("M2 status: awaiting live controller");
        self._panel.Add(self._rosterLabel);
        self._responseLabel = UI.Label("No command sent in this session.");
        self._panel.Add(self._responseLabel);

        self._actions = UI.ScrollView().Height(340);
        self._actions.Add(UI.Label("Recipient:"));
        self._actions.Add(UI.Button("ALL M2 cadets", self.SelectAll));
        self._actions.Add(UI.Button("M2 cadet 1", self.SelectOne));
        self._actions.Add(UI.Button("M2 cadet 2", self.SelectTwo));
        self._actions.Add(UI.Button("M2 cadet 3", self.SelectThree));
        self._actions.Add(UI.Button("M2 cadet 4", self.SelectFour));
        self._actions.Add(UI.Label("Orders:"));
        self._actions.Add(UI.Button("ENGAGE Titans", self.Engage));
        self._actions.Add(UI.Button("ENGAGE + DIRECT", self.EngageDirect));
        self._actions.Add(UI.Button("RUN AUTO HOLD CAPTURE (M2-1)", self.StartAutoHoldTest));
        self._actions.Add(UI.Button("ENGAGE + ENGINE", self.EngageEngine));
        self._actions.Add(UI.Button("EXPLORE map", self.Explore));
        self._actions.Add(UI.Button("HOLD position", self.Hold));
        self._actions.Add(UI.Button("RECOVER + RESUME ENGAGE", self.Recovery));
        self._actions.Add(UI.Button("RESUPPLY now", self.Resupply));
        self._actions.Add(UI.Label("Stand inside a working station trigger:"));
        self._actions.Add(UI.Button("MARK supply here", self.MarkSupply));
        self._actions.Add(UI.Label("Ground pursuit comparison (diagnostic):"));
        self._actions.Add(UI.Button("GROUND: engine steering test", self.GroundEngine));
        self._actions.Add(UI.Button("GROUND: direct steering (default)", self.GroundDirect));
        self._actions.Add(UI.Button("CLOSE & RESTORE [F8/F9]", self.CloseMenu));
        self._panel.Add(self._actions);
        root.Add(self._panel);
        Game.Print("[AI Cadets Orders] F8 opens/closes orders, F9 restores player controls. Cursor-only menu; human movement/ODM inputs are never disabled.");
    }

    # Key polling belongs in OnFrame: GetKeyDown is frame-based.
    function OnFrame()
    {
        if (!self._initialized || !Network.IsMasterClient)
        {
            return;
        }
        if (Input.GetKeyDown(self.RecoveryKey))
        {
            self.CloseMenu();
            Game.Print("[AI Cadets Orders] F9 recovered human controls.");
            return;
        }
        if (Input.GetKeyDown(self.ToggleKey))
        {
            self.ToggleMenu();
        }
        if (self._open && Time.GameTime >= self._nextRefresh)
        {
            self._nextRefresh = Time.GameTime + 0.75;
            self.RefreshStatus();
        }
    }

    # A watchdog is independent of keyboard/UI click delivery. An abandoned
    # panel auto-closes without requiring Pause or a working F8 shortcut.
    function OnTick()
    {
        if (self._initialized && self._open && Time.GameTime - self._openedAt >= self.MenuMaxSeconds)
        {
            self.CloseMenu();
            Game.Print("[AI Cadets Orders] Safety timeout: menu closed and human controls restored.");
        }
        if (self._initialized && self._autoHoldTestStage != "idle" && self._autoHoldTestStage != "complete" && self._autoHoldTestStage != "aborted")
        {
            self.AdvanceAutoHoldTest();
        }
    }

    function RestoreHumanControls()
    {
        # These calls are repair-only. OpenMenu NEVER disables Human keybinds
        # or locks the camera, preventing a stuck menu from seizing control.
        Input.SetHumanKeysEnabled(true);
        Camera.SetCameraLocked(false);
        Camera.SetCursorVisible(false);
    }

    function ToggleMenu()
    {
        if (self._open)
        {
            self.CloseMenu();
            return;
        }
        self.OpenMenu();
    }

    function OpenMenu()
    {
        if (self._panel == null || self._open)
        {
            return;
        }
        self._open = true;
        self._openedAt = Time.GameTime;
        self._panel.Active(true);
        # Cursor-only overlay. Do not globally disable Human controls or
        # lock the camera; F8 input may be swallowed while a UI has focus.
        Camera.SetCursorVisible(true);
        self._nextRefresh = 0.0;
        self.RefreshStatus();
    }

    function CloseMenu()
    {
        if (!self._initialized)
        {
            return;
        }
        self._open = false;
        if (self._panel != null)
        {
            self._panel.Active(false);
        }
        # Unconditional recovery even if the UI state and cursor diverged.
        self.RestoreHumanControls();
    }

    function SelectAll()
    {
        self._selected = "all";
        self._selectedLabel.Text = "Recipient: ALL M2 cadets";
        self.RefreshStatus();
    }

    function SelectOne()
    {
        self.SelectNumber(1);
    }

    function SelectTwo()
    {
        self.SelectNumber(2);
    }

    function SelectThree()
    {
        self.SelectNumber(3);
    }

    function SelectFour()
    {
        self.SelectNumber(4);
    }

    function SelectNumber(number)
    {
        self._selected = "AICadetsM2-" + Convert.ToString(number);
        self._selectedLabel.Text = "Recipient: " + self._selected;
        self.RefreshStatus();
    }

    function Engage()
    {
        self.SendOrder("Engage");
    }

    function EngageDirect()
    {
        self.SendOrder("EngageDirect");
    }

    function EngageEngine()
    {
        self.SendOrder("EngageEngine");
    }

    function Explore()
    {
        self.SendOrder("Explore");
    }

    function Hold()
    {
        self.SendOrder("Hold");
    }

    function Recovery()
    {
        self.SendOrder("Recovery");
    }

    function Resupply()
    {
        self.SendOrder("Resupply");
    }

    function GroundEngine()
    {
        self.SendOrder("GroundEngine");
    }

    function GroundDirect()
    {
        self.SendOrder("GroundDirect");
    }

    function MarkSupply()
    {
        if (!Network.IsMasterClient)
        {
            return;
        }
        host = Network.MyPlayer.Character;
        if (host == null || host.Type != "Human" || !host.IsAlive)
        {
            self._responseLabel.Text = "Supply mark failed: host not alive";
            return;
        }
        point = host.Position;
        PersistentData.SetProperty("AICadetsSupplyX", point.X);
        PersistentData.SetProperty("AICadetsSupplyY", point.Y);
        PersistentData.SetProperty("AICadetsSupplyZ", point.Z);
        self._supplyRevision = self._supplyRevision + 1;
        PersistentData.SetProperty("AICadetsSupplyRevision", self._supplyRevision);
        self._responseLabel.Text = "Supply waypoint marked (not verified)";
        Game.Print("[AI Cadets Orders] supply_marked_unverified point=" + Convert.ToString(point));
    }

    function SendOrder(mode)
    {
        if (!Network.IsMasterClient)
        {
            return;
        }
        if (self._autoHoldTestStage != "idle" && self._autoHoldTestStage != "complete" && self._autoHoldTestStage != "aborted" && !self._autoHoldTestInternalDispatch)
        {
            self.AbortAutoHoldTest("manual_order_interrupted_sequence");
        }
        # A submission is not success. The cadet publishes its own ack later.
        PersistentData.SetProperty("AICadetsCmdScope", self._selected);
        PersistentData.SetProperty("AICadetsCmdMode", mode);
        self._seq = self._seq + 1;
        self._pendingSeq = self._seq;
        self._pendingScope = self._selected;
        self._pendingMode = mode;
        PersistentData.SetProperty("AICadetsCmdSequence", self._seq);
        self._responseLabel.Text = "SENT #" + Convert.ToString(self._seq) + " " + mode + " | waiting for M2 ack";
        Game.Print("[AI Cadets Orders] REQUESTED seq=" + Convert.ToString(self._seq) + " scope=" + self._selected + " mode=" + mode);
        self.RefreshStatus();
    }

    # One button starts a bounded, host-only capture sequence. It waits for a
    # fresh M2-1 controller heartbeat, then for sustained ground pursuit before
    # sending Hold. No character movement is issued by this add-on.
    function StartAutoHoldTest()
    {
        if (!Network.IsMasterClient || self._autoHoldTestStarted)
        {
            return;
        }
        self._autoHoldTestStarted = true;
        self._autoHoldTestBot = "AICadetsM2-1";
        self._selected = self._autoHoldTestBot;
        self._selectedLabel.Text = "Recipient: " + self._selected;
        self._seq = PersistentData.GetProperty("AICadetsCmdSequence", self._seq);
        self._autoHoldTestTrace = "";
        PersistentData.SetProperty("AICadetsM2AutoHoldTestTrace", self._autoHoldTestTrace);
        self._autoHoldTestStage = "wait_controller";
        self._autoHoldTestDeadline = Time.GameTime + 90.0;
        self._autoHoldTestGroundSince = -1.0;
        self._autoHoldTestGroundPathStart = -1.0;
        self._autoHoldTestHoldSince = -1.0;
        self._autoHoldTestHoldPathStart = -1.0;
        self._autoHoldTestResumeGroundSince = -1.0;
        self._autoHoldTestResumePathStart = -1.0;
        self._autoHoldTestTargetId = 0;
        self._autoHoldTestHoldMotionWithin2 = false;
        self.RecordAutoHoldTest("started bot=" + self._autoHoldTestBot);
        self._responseLabel.Text = "AUTO HOLD TEST: waiting for live M2-1";
        Game.Print("[AI Cadets Hold Test] started; waiting for a live M2-1 controller.");
        self.CloseMenu();
    }

    function AdvanceAutoHoldTest()
    {
        if (!Network.IsMasterClient)
        {
            self.AbortAutoHoldTest("master_authority_lost");
            return;
        }
        if (Time.GameTime > self._autoHoldTestDeadline && self._autoHoldTestStage != "hold")
        {
            self.AbortAutoHoldTest("timeout_stage=" + self._autoHoldTestStage);
            return;
        }

        key = self._autoHoldTestBot;
        state = PersistentData.GetProperty("AICadetsM2State-" + key, "UNKNOWN");
        mode = PersistentData.GetProperty("AICadetsM2Mode-" + key, "UNKNOWN");
        target = PersistentData.GetProperty("AICadetsM2TargetId-" + key, 0);
        statusTime = PersistentData.GetProperty("AICadetsM2StatusTime-" + key, -100.0);
        ackSequence = PersistentData.GetProperty("AICadetsM2AckSeq-" + key, -1);
        ackMode = PersistentData.GetProperty("AICadetsM2AckMode-" + key, "UNKNOWN");
        watcherCadet = PersistentData.GetProperty("AICadetsM2WatcherCadet", "");
        observedPath = PersistentData.GetProperty("AICadetsM2ObservedPath-" + key, -1.0);
        observedSampleTime = PersistentData.GetProperty("AICadetsM2ObservedSampleTime-" + key, -100.0);
        observedSampleFresh = observedSampleTime <= Time.GameTime && Time.GameTime - observedSampleTime <= 2.5;

        if (self._autoHoldTestStage == "wait_controller")
        {
            freshHeartbeat = statusTime <= Time.GameTime && Time.GameTime - statusTime <= 2.5;
            watcherReady = PersistentData.GetProperty("AICadetsM2WatcherActive", false);
            watcherFile = PersistentData.GetProperty("AICadetsM2WatcherFile", "");
            if (self.HasOwnedAutoHoldCadet() && freshHeartbeat && watcherReady && watcherCadet == key && watcherFile != "" && PersistentData.FileExists(watcherFile) && observedPath >= 0.0 && observedSampleFresh && PersistentData.GetProperty("AICadetsM2Build-" + key, "unknown") != "unknown")
            {
                self._autoHoldTestDeadline = Time.GameTime + 20.0;
                self.SendAutoHoldTestOrder("EngageDirect");
                self._autoHoldTestStage = "wait_engage_ack";
                self._autoHoldTestDeadline = Time.GameTime + 20.0;
                self.RecordAutoHoldTest("engage_direct_sent seq=" + Convert.ToString(self._autoHoldTestSequence));
                return;
            }
            return;
        }

        if (self._autoHoldTestStage == "wait_engage_ack")
        {
            if (ackSequence == self._autoHoldTestSequence && ackMode == "EngageDirect")
            {
                self._autoHoldTestStage = "wait_ground_pursuit";
                self._autoHoldTestDeadline = Time.GameTime + 60.0;
                self._autoHoldTestGroundSince = -1.0;
                self._autoHoldTestGroundPathStart = -1.0;
                self._autoHoldTestTargetId = 0;
                self.RecordAutoHoldTest("engage_direct_ack state=" + state);
            }
            return;
        }

        if (self._autoHoldTestStage == "wait_ground_pursuit")
        {
            activeGroundPursuit = state == "ApproachGround" && mode == "Engage" && target > 0 && statusTime <= Time.GameTime && Time.GameTime - statusTime <= 2.5;
            if (activeGroundPursuit)
            {
                if (target != self._autoHoldTestTargetId || self._autoHoldTestGroundSince < 0.0 || self._autoHoldTestGroundPathStart < 0.0)
                {
                    self._autoHoldTestTargetId = target;
                    self._autoHoldTestGroundSince = Time.GameTime;
                    self._autoHoldTestGroundPathStart = observedPath;
                    self.RecordAutoHoldTest("ground_pursuit_seen target=" + Convert.ToString(target) + " path=" + Convert.ToString(observedPath));
                }
                elif (observedPath < self._autoHoldTestGroundPathStart)
                {
                    self.AbortAutoHoldTest("watcher_path_reset_during_ground_pursuit");
                    return;
                }
                elif (observedSampleFresh && observedPath >= self._autoHoldTestGroundPathStart + 2.0 && Time.GameTime - self._autoHoldTestGroundSince >= 2.0)
                {
                    self._autoHoldTestDeadline = Time.GameTime + 15.0;
                    self.SendAutoHoldTestOrder("Hold");
                    self._autoHoldTestStage = "wait_hold_ack";
                    self._autoHoldTestDeadline = Time.GameTime + 15.0;
                    self.RecordAutoHoldTest("hold_sent seq=" + Convert.ToString(self._autoHoldTestSequence) + " target=" + Convert.ToString(target) + " path=" + Convert.ToString(observedPath));
                }
            }
            else
            {
                self._autoHoldTestGroundSince = -1.0;
                self._autoHoldTestGroundPathStart = -1.0;
                self._autoHoldTestTargetId = 0;
            }
            return;
        }

        if (self._autoHoldTestStage == "wait_hold_ack")
        {
            if (ackSequence == self._autoHoldTestSequence && ackMode == "Hold" && state == "Hold" && statusTime <= Time.GameTime && Time.GameTime - statusTime <= 2.5 && observedPath >= 0.0 && observedSampleFresh)
            {
                self._autoHoldTestStage = "hold";
                self._autoHoldTestHoldSince = Time.GameTime;
                self._autoHoldTestHoldPathStart = observedPath;
                self.RecordAutoHoldTest("hold_ack state=Hold");
            }
            return;
        }

        if (self._autoHoldTestStage == "hold")
        {
            if (state != "Hold" || statusTime > Time.GameTime || Time.GameTime - statusTime > 2.5 || !self.HasOwnedAutoHoldCadet())
            {
                self.AbortAutoHoldTest("hold_state_interrupted");
                return;
            }
            if (Time.GameTime - self._autoHoldTestHoldSince >= 5.0)
            {
                holdDistance = observedPath - self._autoHoldTestHoldPathStart;
                if (observedPath < self._autoHoldTestHoldPathStart || !observedSampleFresh)
                {
                    self.AbortAutoHoldTest("watcher_motion_sample_stale_or_reset_during_hold");
                    return;
                }
                self._autoHoldTestHoldMotionWithin2 = holdDistance <= 2.0;
                holdOutcome = "over_2_units";
                if (self._autoHoldTestHoldMotionWithin2)
                {
                    holdOutcome = "within_2_units";
                }
                self.RecordAutoHoldTest("hold_motion_observed distance=" + Convert.ToString(holdDistance) + " outcome=" + holdOutcome);
                self._autoHoldTestResumePathStart = observedPath;
                self._autoHoldTestStage = "wait_resume_ack";
                self._autoHoldTestDeadline = Time.GameTime + 20.0;
                self.SendAutoHoldTestOrder("EngageDirect");
                self.RecordAutoHoldTest("resume_engage_direct_sent seq=" + Convert.ToString(self._autoHoldTestSequence));
            }
            return;
        }

        if (self._autoHoldTestStage == "wait_resume_ack")
        {
            if (ackSequence == self._autoHoldTestSequence && ackMode == "EngageDirect")
            {
                self._autoHoldTestStage = "wait_resume_ground";
                self._autoHoldTestDeadline = Time.GameTime + 45.0;
                self.RecordAutoHoldTest("resume_engage_direct_ack state=" + state);
            }
            return;
        }

        if (self._autoHoldTestStage == "wait_resume_ground")
        {
            if (observedPath < self._autoHoldTestResumePathStart)
            {
                self.AbortAutoHoldTest("watcher_path_reset_during_resume");
                return;
            }
            activeGroundPursuit = state == "ApproachGround" && mode == "Engage" && target == self._autoHoldTestTargetId && target > 0 && statusTime <= Time.GameTime && Time.GameTime - statusTime <= 2.5;
            if (activeGroundPursuit)
            {
                if (self._autoHoldTestResumeGroundSince < 0.0)
                {
                    self._autoHoldTestResumeGroundSince = Time.GameTime;
                    self.RecordAutoHoldTest("resumed_ground_pursuit_seen target=" + Convert.ToString(target));
                }
                elif (observedSampleFresh && observedPath >= self._autoHoldTestResumePathStart + 2.0 && Time.GameTime - self._autoHoldTestResumeGroundSince >= 2.0)
                {
                    self._autoHoldTestStage = "complete";
                    self.RecordAutoHoldTest("complete hold_within_2_units=" + Convert.ToString(self._autoHoldTestHoldMotionWithin2) + " resumed_path=" + Convert.ToString(observedPath - self._autoHoldTestResumePathStart) + " target=" + Convert.ToString(target));
                    self._responseLabel.Text = "AUTO HOLD TEST: complete; review watcher trace";
                    Game.Print("[AI Cadets Hold Test] complete; EngageDirect -> Hold -> EngageDirect acknowledged and ground pursuit resumed.");
                }
            }
            else
            {
                self._autoHoldTestResumeGroundSince = -1.0;
            }
        }
    }

    function HasOwnedAutoHoldCadet()
    {
        for (human in Game.AIHumans)
        {
            if (human.Name == self._autoHoldTestBot && human.IsMine && human.IsAlive)
            {
                return true;
            }
        }
        return false;
    }

    function SendAutoHoldTestOrder(mode)
    {
        self._autoHoldTestInternalDispatch = true;
        self._selected = self._autoHoldTestBot;
        self.SendOrder(mode);
        self._autoHoldTestInternalDispatch = false;
        self._autoHoldTestSequence = self._pendingSeq;
    }

    function RecordAutoHoldTest(event)
    {
        line = Convert.ToString(Time.GameTime) + " " + event + "\n";
        self._autoHoldTestTrace = self._autoHoldTestTrace + line;
        PersistentData.SetProperty("AICadetsM2AutoHoldTestTrace", self._autoHoldTestTrace);
        Game.Print("[AI Cadets Hold Test] " + event);
    }

    function AbortAutoHoldTest(reason)
    {
        if (self._autoHoldTestStage == "idle" || self._autoHoldTestStage == "complete" || self._autoHoldTestStage == "aborted")
        {
            return;
        }
        self._autoHoldTestStage = "aborted";
        self.RecordAutoHoldTest("aborted reason=" + reason);
        self._responseLabel.Text = "AUTO HOLD TEST: stopped; " + reason;
        Game.Print("[AI Cadets Hold Test] aborted reason=" + reason);
    }

    function RefreshStatus()
    {
        if (self._panel == null)
        {
            return;
        }
        count = 0;
        other = 0;
        acked = 0;
        stopped = 0;
        unresponsive = 0;
        lines = "";
        for (human in Game.AIHumans)
        {
            if (!human.IsAlive || !human.IsMine)
            {
                continue;
            }
            if (human.Name == "AICadetsM1" || human.Name == "AICadetsM1R")
            {
                other = other + 1;
                continue;
            }
            if (human.Name != "AICadetsM2-1" && human.Name != "AICadetsM2-2" && human.Name != "AICadetsM2-3" && human.Name != "AICadetsM2-4")
            {
                continue;
            }
            count = count + 1;
            name = human.Name;
            lastSeen = PersistentData.GetProperty("AICadetsM2Heartbeat-" + name, -100.0);
            state = PersistentData.GetProperty("AICadetsM2State-" + name, "UNKNOWN");
            reason = PersistentData.GetProperty("AICadetsM2TerminalReason-" + name, "unknown");
            ack = PersistentData.GetProperty("AICadetsM2AckSeq-" + name, 0);
            if (state == "Done")
            {
                stopped = stopped + 1;
                lines = lines + name + " [TERMINATED: " + reason + "] ack=" + Convert.ToString(ack) + "\n";
            }
            else
            {
                if (Time.GameTime - lastSeen > 4.0)
                {
                    state = "NO CONTROLLER HEARTBEAT";
                    unresponsive = unresponsive + 1;
                }
                lines = lines + name + " [" + state + "] ack=" + Convert.ToString(ack) + "\n";
            }
            build = PersistentData.GetProperty("AICadetsM2Build-" + name, "OLD/UNKNOWN - update controller");
            profile = PersistentData.GetProperty("AICadetsM2Profile-" + name, "profile unavailable");
            lines = lines + build + "\n" + profile + "\n";
            if (self._pendingSeq > 0 && ack == self._pendingSeq && (self._pendingScope == "all" || self._pendingScope == name))
            {
                acked = acked + 1;
            }
        }
        if (count == 0)
        {
            lines = "No owned M2 cadets. Enable WaveCadet!\n";
            # Last recorded terminal state is diagnostic only. It may be from
            # a previous lobby, so don't treat it as an active living cadet.
            lastState = PersistentData.GetProperty("AICadetsM2State-AICadetsM2-1", "none");
            if (lastState == "Done")
            {
                reason = PersistentData.GetProperty("AICadetsM2TerminalReason-AICadetsM2-1", "unknown");
                lines = lines + "Previous M2-1 ended: " + reason + "\n";
            }
        }
        if (other > 0)
        {
            lines = lines + "M1 demo bots: " + Convert.ToString(other) + " (not controllable; disable M1 addons for M2 test)\n";
        }
        self._rosterLabel.Text = lines;
        if (self._pendingSeq > 0)
        {
            if (acked > 0)
            {
                self._responseLabel.Text = "APPLIED #" + Convert.ToString(self._pendingSeq) + " " + self._pendingMode + " by " + Convert.ToString(acked) + " M2 cadet(s)";
                if (self._reportedAckSeq != self._pendingSeq)
                {
                    self._reportedAckSeq = self._pendingSeq;
                    Game.Print("[AI Cadets Orders] APPLIED seq=" + Convert.ToString(self._pendingSeq) + " mode=" + self._pendingMode + " confirmed_by=" + Convert.ToString(acked));
                }
            }
            if (acked == 0)
            {
                if (count == 0)
                {
                    self._responseLabel.Text = "NOT APPLIED #" + Convert.ToString(self._pendingSeq) + ": no owned M2 cadet";
                }
                elif (stopped == count)
                {
                    self._responseLabel.Text = "NOT APPLIED #" + Convert.ToString(self._pendingSeq) + ": controller terminated";
                }
                elif (unresponsive == count)
                {
                    self._responseLabel.Text = "NOT APPLIED #" + Convert.ToString(self._pendingSeq) + ": no live heartbeat";
                }
                else
                {
                    self._responseLabel.Text = "PENDING #" + Convert.ToString(self._pendingSeq) + " " + self._pendingMode + " | waiting for M2 ack";
                }
            }
        }
    }

    function OnGameEnd()
    {
        self.CloseMenu();
        if (self._panel != null)
        {
            self._panel.RemoveFromHierarchy();
            self._panel = null;
        }
        self._initialized = false;
        self._pendingSeq = 0;
    }
}
