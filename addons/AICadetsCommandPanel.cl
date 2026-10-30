# Optional M2 command panel. This addon never moves cadets itself.
# Commands are stored as transient (unsaved) shared PersistentData values.
addon AICadetsCommandPanel
{
    Description = "Host-only local M2 cadet orders: All / individual, Engage / Explore / Hold.";
    _initialized = false;
    _panel = null;
    _selected = "all";
    _selectedLabel = null;
    _seq = 0;
    _supplyRevision = 0;

    function OnGameStart()
    {
        if (self._initialized || !Network.IsMasterClient)
        {
            return;
        }
        self._initialized = true;
        self._seq = PersistentData.GetProperty("AICadetsCmdSequence", 0);
        self._supplyRevision = PersistentData.GetProperty("AICadetsSupplyRevision", 0);
        root = UI.GetRootVisualElement();
        self._panel = UI.VisualElement().Absolute(true).Right(16).Top(100).Width(230).Padding(8);
        self._panel.Add(UI.Label("AI Cadets M2 Orders"));
        self._selectedLabel = UI.Label("Target: All cadets");
        self._panel.Add(self._selectedLabel);
        self._panel.Add(UI.Label("Select recipients:"));
        self._panel.Add(UI.Button("All cadets", self.SelectAll));
        self._panel.Add(UI.Button("M2 Cadet 1", self.SelectOne));
        self._panel.Add(UI.Button("M2 Cadet 2", self.SelectTwo));
        self._panel.Add(UI.Button("M2 Cadet 3", self.SelectThree));
        self._panel.Add(UI.Button("M2 Cadet 4", self.SelectFour));
        self._panel.Add(UI.Label("Issue instruction:"));
        self._panel.Add(UI.Button("ENGAGE Titans", self.Engage));
        self._panel.Add(UI.Button("EXPLORE map", self.Explore));
        self._panel.Add(UI.Button("HOLD position", self.Hold));
        self._panel.Add(UI.Button("RESUPPLY now", self.Resupply));
        self._panel.Add(UI.Label("Stand at a real station before marking:"));
        self._panel.Add(UI.Button("MARK supply here", self.MarkSupply));
        root.Add(self._panel);
        Game.Print("[AI Cadets Orders] Host panel ready. Select All or one M2 cadet, then issue an instruction.");
    }

    function SelectAll()
    {
        self._selected = "all";
        self._selectedLabel.Text = "Target: All cadets";
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
        self._selectedLabel.Text = "Target: " + self._selected;
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
            Game.Print("[AI Cadets Orders] Supply mark requires an alive host at a real station.");
            return;
        }
        point = host.Position;
        # Write a coherent station bookmark; revision is the commit marker.
        # Bookmarks are hints only. Actual refilling must occur through the
        # SupplyStation's native collision/AutoRefillGas behavior.
        PersistentData.SetProperty("AICadetsSupplyX", point.X);
        PersistentData.SetProperty("AICadetsSupplyY", point.Y);
        PersistentData.SetProperty("AICadetsSupplyZ", point.Z);
        self._supplyRevision = self._supplyRevision + 1;
        PersistentData.SetProperty("AICadetsSupplyRevision", self._supplyRevision);
        Game.Print("[AI Cadets Orders] supply_marked_unverified point=" + Convert.ToString(point));
    }

    function SendOrder(mode)
    {
        if (!Network.IsMasterClient)
        {
            return;
        }
        # Write scope + mode before the sequence, which is the commit marker.
        PersistentData.SetProperty("AICadetsCmdScope", self._selected);
        PersistentData.SetProperty("AICadetsCmdMode", mode);
        self._seq = self._seq + 1;
        PersistentData.SetProperty("AICadetsCmdSequence", self._seq);
        Game.Print("[AI Cadets Orders] scope=" + self._selected + " mode=" + mode + " seq=" + Convert.ToString(self._seq));
    }

    function OnGameEnd()
    {
        if (self._panel != null)
        {
            self._panel.RemoveFromHierarchy();
            self._panel = null;
        }
    }
}
