# Opt-in diagnostic observer for AICadetsTraversal. No character mutations.
addon AICadetsWatcher
{
    Description = "Record one AI Cadets M1 attempt to a local persistent-data file.";
    _scout = null;
    _trace = "";
    _file = "";
    _started = false;
    _finished = false;
    _nextSample = 0.0;
    _nextSave = 0.0;
    _start = 0.0;
    _foundAt = 0.0;
    _lastHook = false;
    _lastHooking = false;
    _lastGrounded = false;

    function OnGameStart()
    {
        if (self._started)
        {
            return;
        }
        self._started = true;
        if (!Network.IsMasterClient)
        {
            self._finished = true;
            return;
        }
        # Never overwrite an existing diagnostic. Bounded search, 100 files.
        for (i in Range(0, 100, 1))
        {
            candidate = "AICadetsM1Watch" + Convert.ToString(i);
            if (!PersistentData.FileExists(candidate))
            {
                self._file = candidate;
                break;
            }
        }
        if (self._file == "")
        {
            self._finished = true;
            Game.Print("[AI Cadets Watch] No free file slot; archive old watch files.");
            return;
        }
        self._start = Time.GameTime;
        self._trace = "AICadetsWatcher v1; times=GameTime; samples=0.2s; max=25s after discovery\n";
        self.Record("watch_started");
        self.Flush();
        Game.Print("[AI Cadets Watch] Recording to PersistentData/" + self._file);
    }

    function OnTick()
    {
        if (self._finished || !self._started)
        {
            return;
        }
        if (!Network.IsMasterClient)
        {
            self.Record("master_lost");
            self.Flush();
            self._finished = true;
            return;
        }
        if ((self._scout == null && Time.GameTime - self._start >= 45.0) || (self._scout != null && Time.GameTime - self._foundAt >= 25.0))
        {
            self.Record("watch_timeout");
            self.Flush();
            self._finished = true;
            Game.Print("[AI Cadets Watch] Recording saved: " + self._file);
            return;
        }
        if (self._scout == null)
        {
            for (human in Game.AIHumans)
            {
                if (human.Name == "AICadetsM1" && human.IsMine)
                {
                    self._scout = human;
                    self._foundAt = Time.GameTime;
                    self.Record("scout_found");
                    self.Flush();
                    break;
                }
            }
            return;
        }
        if (!self._scout.IsAlive)
        {
            self.Record("scout_dead_or_despawned");
            self.Flush();
            self._finished = true;
            return;
        }
        if (!self._scout.IsMine)
        {
            self.Record("ownership_lost");
            self.Flush();
            self._finished = true;
            return;
        }
        if (self._scout.IsHookedLeft != self._lastHook || self._scout.IsHookingLeft != self._lastHooking || self._scout.Grounded != self._lastGrounded)
        {
            self.Snapshot("change");
            self._lastHook = self._scout.IsHookedLeft;
            self._lastHooking = self._scout.IsHookingLeft;
            self._lastGrounded = self._scout.Grounded;
        }
        if (Time.GameTime >= self._nextSample)
        {
            self.Snapshot("sample");
            self._nextSample = Time.GameTime + 0.2;
        }
        if (Time.GameTime >= self._nextSave)
        {
            self.Flush();
        }
    }

    function Record(event)
    {
        self._trace = self._trace + Convert.ToString(Time.GameTime) + " " + event + "\n";
    }

    function Snapshot(kind)
    {
        hookpos = "none";
        if (self._scout.LeftHookPosition != null)
        {
            hookpos = Convert.ToString(self._scout.LeftHookPosition);
        }
        self.Record(kind + " pos=" + Convert.ToString(self._scout.Position) + " vel=" + Convert.ToString(self._scout.Velocity) + " gas=" + Convert.ToString(self._scout.CurrentGas) + " hooked=" + Convert.ToString(self._scout.IsHookedLeft) + " hooking=" + Convert.ToString(self._scout.IsHookingLeft) + " ready=" + Convert.ToString(self._scout.LeftHookReady) + " grounded=" + Convert.ToString(self._scout.Grounded) + " hookpos=" + hookpos);
    }

    function Flush()
    {
        # Do not Clear(): PersistentData is shared with other scripts.
        PersistentData.SetProperty("AICadetsM1WatchTrace", self._trace);
        PersistentData.SaveToFile(self._file, false);
        self._nextSave = Time.GameTime + 1.0;
    }
}
