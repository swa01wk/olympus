# AppShell

Application frame: top bar (wordmark, project, cycle picker, stream state, New delivery cycle, Ask Olympus) and the monogram rail.

- **Provide:** `screen`, `journey`, `stage`, `onNav`, `onCycle`, `onAsk`, `onNew`, `stream` (`live` | `disconnected`), `overlay` (dialogs/drawers), children (the screen).
- The `MAP` item is the hub and is visually boxed; drill-down monograms are lane codes and carry an attention flag when their lane needs the operator.
- Switching the cycle picker switches the journey for every screen.
