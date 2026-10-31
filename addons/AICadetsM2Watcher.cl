# Opt-in passive M2 observer. No character mutations.
addon AICadetsM2Watcher
{
    Description = "Record one AI Cadets M2 attempt to a local persistent-data file.";
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
    _previousTime = 0.0;
    _dirty = false;
    _records = 0;
    _nextRoster = 0.0;

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
            candidate = "AICadetsM2Watch" + Convert.ToString(i);
            if (!PersistentData.FileExists(candidate))
            {
                self._file = candidate;
                break;
            }
        }
        if (self._file == "")
        {
            self._finished = true;
            Game.Print("[AI Cadets M2 Watch] No free file slot; archive old watch files.");
            return;
        }
        self._start = Time.GameTime;
        self._trace = "AICadetsM2Watcher v3 navdiag-3; times=GameTime; moving=0.2s; idle=2s; max_records=2000; max=300s after discovery\n";
        self.Record("watch_started");
        self.Flush();
        Game.Print("[AI Cadets M2 Watch] Recording to PersistentData/" + self._file);
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
        if ((self._scout == null && Time.GameTime - self._start >= 45.0) || (self._scout != null && Time.GameTime - self._foundAt >= 300.0))
        {
            self.Record("watch_timeout");
            self.Flush();
            self._finished = true;
            Game.Print("[AI Cadets M2 Watch] Recording saved: " + self._file);
            return;
        }
        if (self._scout == null)
        {
            for (human in Game.AIHumans)
            {
                if ((human.Name == "AICadetsM2-1" || human.Name == "AICadetsM2-2" || human.Name == "AICadetsM2-3" || human.Name == "AICadetsM2-4") && human.IsMine)
                {
                    self._scout = human;
                    self._foundAt = Time.GameTime;
                    self.Record("scout_found cadet=" + self._scout.Name + " run=" + PersistentData.GetProperty("AICadetsM2RunId-" + self._scout.Name, "unknown"));
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
        if (Time.GameTime >= self._nextRoster)
        {
            self._nextRoster = Time.GameTime + 10.0;
            for (human in Game.AIHumans)
            {
                if (human.IsMine && (human.Name == "AICadetsM1" || human.Name == "AICadetsM1R" || human.Name == "AICadetsM2-1" || human.Name == "AICadetsM2-2" || human.Name == "AICadetsM2-3" || human.Name == "AICadetsM2-4"))
                {
                    self.Record("owned_cadet name=" + human.Name + " view_id=" + Convert.ToString(human.ViewID) + " alive=" + Convert.ToString(human.IsAlive) + " controller_state=" + PersistentData.GetProperty("AICadetsM2State-" + human.Name, "no_M2_controller") + " build=" + PersistentData.GetProperty("AICadetsM2Build-" + human.Name, "unknown") + " profile=" + PersistentData.GetProperty("AICadetsM2Profile-" + human.Name, "unknown"));
                }
            }
        }
        self.CheckImpact();
        if (self._scout.IsHookedLeft != self._lastHook || self._scout.IsHookingLeft != self._lastHooking || self._scout.Grounded != self._lastGrounded)
        {
            self.Snapshot("change");
            self._nextSample = Time.GameTime + 0.2;
            self._lastHook = self._scout.IsHookedLeft;
            self._lastHooking = self._scout.IsHookingLeft;
            self._lastGrounded = self._scout.Grounded;
        }
        if (Time.GameTime >= self._nextSample)
        {
            self.Snapshot("sample");
            self._nextSample = Time.GameTime + self.SampleInterval();
        }
        if (self._dirty && Time.GameTime >= self._nextSave)
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
                kind = self.MotionEvent(self._lastHook, self._scout.IsHookedLeft, self._lastGrounded, self._scout.Grounded, hit != null);
                self.Record(kind + " dt=" + Convert.ToString(Time.GameTime - self._previousTime) + " pre_pos=" + Convert.ToString(self._previousPosition) + " pos=" + Convert.ToString(position) + " pre_vel=" + Convert.ToString(self._previousVelocity) + " post_vel=" + Convert.ToString(velocity) + " delta_v=" + Convert.ToString(change) + " " + detail);
                self._nextImpact = Time.GameTime + 1.0;
            }
        }
        self._previousVelocity = velocity;
        self._previousPosition = position;
        self._previousTime = Time.GameTime;
    }

    function SampleInterval()
    {
        if (self._scout.Grounded && self._scout.Velocity.Magnitude < 0.1 && !self._scout.IsHookedLeft && !self._scout.IsHookingLeft)
        {
            return 2.0;
        }
        return 0.2;
    }

    function MotionEvent(wasHooked, hooked, wasGrounded, grounded, mapHit)
    {
        if (!wasGrounded && grounded)
        {
            return "landing_velocity_change";
        }
        if (wasHooked != hooked)
        {
            if (mapHit)
            {
                return "hook_transition_near_surface";
            }
            return "hook_transition_velocity_change";
        }
        if (mapHit)
        {
            return "possible_impact";
        }
        return "unexplained_velocity_change";
    }

    function Record(event)
    {
        if (self._records >= 2000)
        {
            return;
        }
        self._records = self._records + 1;
        self._dirty = true;
        if (self._records == 2000)
        {
            event = "record_limit_reached";
            self._finished = true;
        }
        self._trace = self._trace + Convert.ToString(Time.GameTime) + " " + event + "\n";
        if (self._finished)
        {
            self.Flush();
        }
    }

    function Snapshot(kind)
    {
        hookpos = "none";
        if (self._scout.LeftHookPosition != null)
        {
            hookpos = Convert.ToString(self._scout.LeftHookPosition);
        }
        self.Record(kind + " cadet=" + self._scout.Name + " status_time=" + Convert.ToString(PersistentData.GetProperty("AICadetsM2StatusTime-" + self._scout.Name, 0.0)) + " target=" + Convert.ToString(PersistentData.GetProperty("AICadetsM2TargetId-" + self._scout.Name, 0)) + " target_info=[" + PersistentData.GetProperty("AICadetsM2TargetInfo-" + self._scout.Name, "none") + "] nav=[" + PersistentData.GetProperty("AICadetsM2Navigation-" + self._scout.Name, "none") + "] mode=" + PersistentData.GetProperty("AICadetsM2Mode-" + self._scout.Name, "unknown") + " state=" + PersistentData.GetProperty("AICadetsM2State-" + self._scout.Name, "unknown") + " ai_state=" + self._scout.GetAIState() + " pos=" + Convert.ToString(self._scout.Position) + " vel=" + Convert.ToString(self._scout.Velocity) + " gas=" + Convert.ToString(self._scout.CurrentGas) + " hooked=" + Convert.ToString(self._scout.IsHookedLeft) + " hooking=" + Convert.ToString(self._scout.IsHookingLeft) + " ready=" + Convert.ToString(self._scout.LeftHookReady) + " grounded=" + Convert.ToString(self._scout.Grounded) + " hookpos=" + hookpos);
    }

    function Flush()
    {
        # Do not Clear(): PersistentData is shared with other scripts.
        PersistentData.SetProperty("AICadetsM2WatchTrace", self._trace);
        PersistentData.SaveToFile(self._file, false);
        self._nextSave = Time.GameTime + 1.0;
        self._dirty = false;
    }
}
