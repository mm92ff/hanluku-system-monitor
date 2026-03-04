# Changelog

All notable changes to this project will be documented in this file.

The latest tagged version currently available in the repository is `v1.0-beta`.

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
