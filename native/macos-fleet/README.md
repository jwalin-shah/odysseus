# FleetViewer

A macOS menu bar app (`LSUIElement`, no dock icon) for captains running the
firstmate fleet. It shows live inflight/queued/blocked crewmate tasks and
click-to-focuses the corresponding tmux window.

## Build

```bash
cd native/macos-fleet
swift build            # debug
swift build -c release # release
```

The executable is emitted to `.build/debug/FleetViewer` (or
`.build/release/FleetViewer`). It does not require a `.xcodeproj`.

## Run

```bash
.build/debug/FleetViewer
```

A `person.3` SF Symbol appears in the menu bar with a count of inflight tasks
(`working:` or `starting:`). Click to open the popover, which lists tasks in
order:

1. Inflight (blue)
2. Blocked (red)
3. Queued (orange)
4. Done (recent 5, green)

Clicking a row runs `tmux select-window -t <task.window>` and brings Ghostty
(or any other terminal) forward.

## State file format

`~/projects/firstmate/state/<id>.status` — FleetViewer reads the last line and
parses `<prefix>: <body>` (e.g. `working: branch created`).

`~/projects/firstmate/state/<id>.meta` — key=value pairs. FleetViewer reads
`window`, `repo`, `kind`, `harness`.

## Notifications

FleetViewer requests `.alert + .sound` authorization on first run. It fires
`UNUserNotificationCenter` notifications on transitions into `done:` or
`blocked:`.

## Layout

```
native/macos-fleet/
  Package.swift
  Resources/Info.plist       ← LSUIElement=YES
  Sources/
    FleetCore/
      StateReader.swift      ← fsevents + 3s fallback polling
      Task.swift             ← value type
    FleetViewerApp/
      AppDelegate.swift      ← status bar, popover, focus, notification glue
      FleetListView.swift    ← SwiftUI popover content
      FleetViewerApp.swift   ← @main entry
      Notifications.swift    ← UNUserNotificationCenter wrapper
```
