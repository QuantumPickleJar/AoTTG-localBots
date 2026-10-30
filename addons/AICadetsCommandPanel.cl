# F8-toggle host-only command console for living M2 cadets.
# UI submissions are NOT acknowledgements; only the cadet controller writes
# AICadetsM2AckSeq-<bot name> after it accepts a command.
addon AICadetsCommandPanel
{
    Description = "F8 tactical orders: scoped M2 Engage / Explore / Hold / Resupply, supply marking and acknowledgements.";
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
    _pendingMode = "none";
    _pendingScope = "all";
    _nextRefresh = 0.0;
    _supplyRevision = 0;

    function OnGameStart()
    {
        if (self._initialized || !Network.IsMasterClient)
        {
            return;
        }
        self._initialized = true;
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
        self._actions.Add(UI.Button("EXPLORE map", self.Explore));
        self._actions.Add(UI.Button("HOLD position", self.Hold));
        self._actions.Add(UI.Button("RESUPPLY now", self.Resupply));
        self._actions.Add(UI.Label("Stand inside a working station trigger:"));
        self._actions.Add(UI.Button("MARK supply here", self.MarkSupply));
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

    function Explore()
    {
        self.SendOrder("Explore");
    }

    function Hold()
    {
        self.SendOrder("Hold");
    }

    function Resupply()
    {
        self.SendOrder("Resupply");
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
        # A submission is not success. The cadet publishes its own ack later.
        PersistentData.SetProperty("AICadetsCmdScope", self._selected);
        PersistentData.SetProperty("AICadetsCmdMode", mode);
        self._seq = self._seq + 1;
        self._pendingSeq = self._seq;
        self._pendingScope = self._selected;
        self._pendingMode = mode;
        PersistentData.SetProperty("AICadetsCmdSequence", self._seq);
        self._responseLabel.Text = "SENT #" + Convert.ToString(self._seq) + " " + mode + " | waiting for M2 ack";
        Game.Print("[AI Cadets Orders] submitted seq=" + Convert.ToString(self._seq) + " scope=" + self._selected + " mode=" + mode + " (not yet applied)");
        self.RefreshStatus();
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
            ack = PersistentData.GetProperty("AICadetsM2AckSeq-" + name, 0);
            if (Time.GameTime - lastSeen > 4.0)
            {
                state = "NO CONTROLLER HEARTBEAT";
            }
            lines = lines + name + " [" + state + "] ack=" + Convert.ToString(ack) + "\n";
            if (self._pendingSeq > 0 && ack == self._pendingSeq && (self._pendingScope == "all" || self._pendingScope == name))
            {
                acked = acked + 1;
            }
        }
        if (count == 0)
        {
            lines = "No owned M2 cadets. Enable WaveCadet!\n";
        }
        if (other > 0)
        {
            lines = lines + "M1 demo bots: " + Convert.ToString(other) + " (not controllable)\n";
        }
        self._rosterLabel.Text = lines;
        if (self._pendingSeq > 0)
        {
            if (acked > 0)
            {
                self._responseLabel.Text = "APPLIED #" + Convert.ToString(self._pendingSeq) + " " + self._pendingMode + " by " + Convert.ToString(acked) + " M2 cadet(s)";
            }
            if (acked == 0)
            {
                self._responseLabel.Text = "PENDING #" + Convert.ToString(self._pendingSeq) + " " + self._pendingMode + " | no M2 ack";
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
