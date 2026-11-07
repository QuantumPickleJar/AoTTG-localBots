# Low-rate Custom Logic fallback observer for one isolated primitive probe.
# It is not a physics-step recorder and cannot confirm Unity contact callbacks.
addon AICadetsPrimitiveObserver
{
    Description = "Opt-in passive low-rate observer for AICadetsPrimitiveProbe; REC-I replacement is not available.";
    RunObserver = false;
    RunObserverTooltip = "Leave false unless paired with the isolated primitive probe in a private lobby.";

    _started = false;
    _finished = false;
    _probe = null;
    _file = "";
    _trace = "";
    _records = 0;
    _start = 0.0;
    _foundAt = 0.0;
    _nextSample = 0.0;
    _nextSave = 0.0;
    _lastGrounded = false;
    _lastHooked = false;
    _dirty = false;

    function OnGameStart()
    {
        if (self._started || !self.RunObserver)
        {
            return;
        }
        self._started = true;
        if (!Network.IsMasterClient)
        {
            self._finished = true;
            return;
        }
        for (i in Range(0, 100, 1))
        {
            candidate = "AICadetsPrimitiveWatch" + Convert.ToString(i);
            if (!PersistentData.FileExists(candidate))
            {
                self._file = candidate;
                break;
            }
        }
        if (self._file == "")
        {
            self._finished = true;
            Game.Print("[AI Cadets Primitive Watch] No free output slot; archive old files.");
            return;
        }
        self._start = Time.GameTime;
        self._trace = "AICadetsPrimitiveObserver v1; source=CustomLogic; sample_interval=0.1s; phase=unverified; max_records=600\n";
        self.Record("observer_started");
        self.Flush();
        Game.Print("[AI Cadets Primitive Watch] Passive fallback recording to PersistentData/" + self._file + ". Not physics-step complete.");
    }

    function OnTick()
    {
        if (!self.RunObserver || self._finished || !self._started)
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
        if (Time.GameTime - self._start >= 90.0)
        {
            self.Record("observer_timeout");
            self.Flush();
            self._finished = true;
            Game.Print("[AI Cadets Primitive Watch] Recording stopped at 90 seconds: " + self._file);
            return;
        }
        if (self._probe == null)
        {
            probeId = PersistentData.GetProperty("AICadetsPrimitiveViewID", 0);
            if (probeId != 0)
            {
                for (human in Game.AIHumans)
                {
                    if (human.ViewID == probeId && human.IsMine)
                    {
                        self._probe = human;
                        self._foundAt = Time.GameTime;
                        self.Record("probe_found view_id=" + Convert.ToString(human.ViewID));
                        self.Flush();
                        break;
                    }
                }
            }
            if (self._probe == null && Time.GameTime - self._start >= 20.0)
            {
                self.Record("probe_not_found");
                self.Flush();
                self._finished = true;
                return;
            }
            return;
        }
        if (!self._probe.IsAlive || !self._probe.IsMine)
        {
            self.Record("probe_dead_or_ownership_lost");
            self.Flush();
            self._finished = true;
            return;
        }
        if (Time.GameTime >= self._nextSample)
        {
            self.Snapshot("sample");
            self._nextSample = Time.GameTime + 0.1;
        }
        if (self._probe.Grounded != self._lastGrounded || self._probe.IsHookedLeft != self._lastHooked)
        {
            self.Snapshot("state_change");
            self._lastGrounded = self._probe.Grounded;
            self._lastHooked = self._probe.IsHookedLeft;
        }
        if (self._dirty && Time.GameTime >= self._nextSave)
        {
            self.Flush();
        }
    }

    function Snapshot(kind)
    {
        self.Record(kind + " t=" + Convert.ToString(Time.GameTime) + " view_id=" + Convert.ToString(self._probe.ViewID) + " pos=" + Convert.ToString(self._probe.Position) + " vel=" + Convert.ToString(self._probe.Velocity) + " gas=" + Convert.ToString(self._probe.CurrentGas) + " grounded=" + Convert.ToString(self._probe.Grounded) + " state=" + self._probe.State + " animation=" + self._probe.CurrentAnimation + " hooked_left=" + Convert.ToString(self._probe.IsHookedLeft) + " hooking_left=" + Convert.ToString(self._probe.IsHookingLeft));
    }

    function Record(event)
    {
        if (self._records >= 600)
        {
            self.Flush();
            self._finished = true;
            return;
        }
        self._records = self._records + 1;
        self._dirty = true;
        self._trace = self._trace + Convert.ToString(Time.GameTime) + " " + event + "\n";
    }

    function Flush()
    {
        if (self._file == "")
        {
            return;
        }
        PersistentData.SetProperty("AICadetsPrimitiveWatchTrace", self._trace);
        PersistentData.SaveToFile(self._file, false);
        self._nextSave = Time.GameTime + 1.0;
        self._dirty = false;
    }
}
