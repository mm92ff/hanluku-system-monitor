# Changelog

All notable changes to this project will be documented in this file.

The latest tagged version currently available in the repository is `v1.1.0-beta`.

## [Unreleased]

### Changed

- Merged font controls into `Customize Widget Appearance`, including `Font`, `Font Size`, and `Bold`.
- Added a quick-select dropdown for built-in `Fira Code` variants plus an in-dialog note that `Fira Code` fonts are bundled with the app.
- Widget width preview now auto-scales when font size, font family, or font weight changes.
- Width changes from `Widget Width` in `Customize Widget Appearance` now keep per-widget width differences in horizontal stacks instead of resetting members to one uniform fallback width.
- Added content-aware minimum width clamping so widget width cannot shrink below visible text requirements, preventing label/value overlap.
- Content minimum width for dynamic value widgets (for example `Network` and `Disk I/O`) now respects display mode, so hidden value parts no longer force unnecessary minimum width.
- Added `Widget Appearance...` to the widget right-click menu for faster access.
- Added `Stack Width...` in the widget right-click menu for horizontal stack groups.
- `Stack Width...` now uses a slider dialog with live width preview while dragging and restore-on-cancel behavior.

### Removed

- Removed the separate `Font Settings` dialog window.
- Removed the standalone `Font...` tray menu entry from Display Settings.

## [v1.1.0-beta]

### Changed

- Corrected `Adjust Width` behavior for grouped widgets.
- Vertical stack groups still keep a synchronized shared width.
- Horizontal stack groups now allow per-widget width adjustments.
- Right-click width adjustment now changes only the selected widget in horizontal stack groups.
- The `Add...` button in `Custom Sensor Management` now opens the `Sensor Explorer` instead of starting with manual identifier entry.

### Improved

- Open `Custom Sensor Management` windows now refresh automatically after custom sensor changes.
- Table refresh behavior now preserves selection more reliably after custom sensor add/edit operations.
- Custom sensors added from the `Sensor Explorer` now store `hardware_name` and `sensor_name` consistently.
- The Windows EXE build now uses the project icon from `assets/icons/phoenix_outline_on_dark.ico`.

### Tests

- Added regression coverage for vertical vs. horizontal stack width adjustment behavior.
- Added UI coverage for the updated custom sensor add flow.
- Added UI coverage for automatic refresh of `Custom Sensor Management` after sensor explorer additions.

## [v1.0-beta]

- Initial tagged beta release.
