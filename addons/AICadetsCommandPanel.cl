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

    function OnGameStart()
    {
        if (self._initialized || !Network.IsMasterClient)
        {
            return;
        }
        self._initialized = true;
        self._seq = PersistentData.GetProperty("AICadetsCmdSequence", 0);
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
