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
    _previousVelocity = null;
    _previousPosition = null;
    _nextImpact = 0.0;

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
        self._trace = "AICadetsWatcher v2; times=GameTime; samples=0.2s; max=25s after discovery\n";
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
        self.CheckImpact();
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

    # A change in velocity is only a clue, not a collision callback.
    function CheckImpact()
    {
        velocity = self._scout.Velocity;
        position = self._scout.Position;
        if (self._previousVelocity != null && self._previousPosition != null && Time.GameTime >= self._nextImpact)
        {
            difference = velocity - self._previousVelocity;
            change = difference.Magnitude;
            if (change >= 8.0 && self._previousVelocity.Magnitude >= 5.0)
            {
                start = self._previousPosition + Vector3(0.0, 1.0, 0.0);
                end = position + Vector3(0.0, 1.0, 0.0) + self._previousVelocity.Normalized * 3.0;
                mapHit = Physics.LineCast(start, end, CollideWithEnum.MapObjects);
                editorHit = Physics.LineCast(start, end, CollideWithEnum.MapEditor);
                hit = mapHit;
                layer = "MapObjects";
                if (hit == null || (editorHit != null && editorHit.Distance < hit.Distance))
                {
                    hit = editorHit;
                    layer = "MapEditor";
                }
                detail = "map_hit=none";
                if (hit != null)
                {
                    detail = "layer=" + layer + " hit=" + Convert.ToString(hit.Point) + " normal=" + Convert.ToString(hit.Normal) + " distance=" + Convert.ToString(hit.Distance);
                }
                self.Record("possible_impact pre_pos=" + Convert.ToString(self._previousPosition) + " pos=" + Convert.ToString(position) + " pre_vel=" + Convert.ToString(self._previousVelocity) + " post_vel=" + Convert.ToString(velocity) + " delta_v=" + Convert.ToString(change) + " " + detail);
                self._nextImpact = Time.GameTime + 0.2;
            }
        }
        self._previousVelocity = velocity;
        self._previousPosition = position;
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
