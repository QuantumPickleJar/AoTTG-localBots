# M3 primitive API evidence and validation status

**Status:** command names and signatures are documented; physical effects remain unvalidated in the current AoTTG2 build. No Unity recorder or client-side check has been run in this environment.

The API source is the official Custom Logic documentation at revision [`38796d52a99c2dd76ec08a111395628a9151d07e`](https://github.com/AoTTG-2/CustomLogicDocumentation/tree/38796d52a99c2dd76ec08a111395628a9151d07e), integrated October 31, 2026. That documentation update does not prove that the user's installed game binary shipped those changes. The probe is an optional Custom Logic add-on; it is not a Unity DLL or native instrumentation plugin.

| Documented API | Exact documented signature or field | What the probe can establish | Still needs in-game measurement |
|---|---|---|---|
| `Human.Dodge` | `function Dodge()`; `CanDodge: bool` | An opted-in command was issued when `CanDodge` was true | State transition, impulse, cooldown, gas cost, landing and interruption |
| `Human.Jump` | `function Jump()` | Command and subsequent sampled state | Takeoff timing, impulse, eligibility and landing |
| `Human.Dash` | `function Dash(direction: Vector3)` | Direction passed to the command | Direction convention, impulse, gas cost, cooldown, ground/air rules |
| `Human.UseGas` | `function UseGas(useGas: bool)` | A bounded 0.25 second input pulse | Whether the pulse moves the actor, exact resource cost and interruption behavior |
| `Human.Move` | `function Move(direction: Vector3)` | Bounded ground steering input | Path tracking, collision handling and actual displacement |
| `Human.LaunchHookLeft` | `function LaunchHookLeft(aimPoint: Vector3)` | One left-hook command and observed hook state | Anchor classification, attach timing, tether physics, gas and recovery |
| `Human.ReleaseHookLeft` | `function ReleaseHookLeft()` | Release input and later sampled hook state | Tether cleanup, momentum and safe landing |
| `Human.CurrentGas`, `Character.Position/Velocity`, `Human.State/Grounded` | Read-only documented fields | Low-rate before/after measurements | Full physics-step trajectory and verified simulation phase |

The probe has one `TestCase` setting per run, `RunTest=false` by default, a 10-second grounded-start bound, a 1.5-second jump-to-airborne bound, a 3-second hook-attach bound, and explicit gas/hook/input cleanup. It never writes position, velocity, health, gas, special, collision, or ownership. `HookLeft` covers a single hook only; a two-hook probe should wait until the single-hook and observer path is measured. M0's earlier two-anchor run is separate evidence and does not validate every new primitive.

The companion `AICadetsPrimitiveObserver` samples at 0.1 seconds, saves bounded local data, and captures only one master-owned test actor. It is a low-rate Custom Logic fallback, not an engine telemetry source: it cannot prove complete physics-step coverage, read actual collision callbacks, or distinguish every impulse. Until REC-I passes, a short calibration video remains required for field validation and the session is provisional.

## Present gate

The user's current installation, Unity build, scripting backend, installed loader, and compatibility/rules are not available in this workspace. Therefore no native recorder package is supplied and no REC-I or PRIM-I gameplay pass is claimed. Do not run the PRIM-I card until a recorder has passed REC-I, or explicitly downgrade it to provisional evidence if the project owner chooses to proceed without engine telemetry.

The documented special fields `Human.CurrentSpecial`, `Human.SpecialCooldown`, `Human.SpecialCooldownRatio`, and `Human.IsCarried`, plus `SpecialEnum.Carry`, support future eligibility observation. They do not establish that a special is equipped, ready, activatable, or physically successful in the current build. No primitive probe activates a special.
