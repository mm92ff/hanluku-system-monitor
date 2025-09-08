# hanluku-system-monitor
A highly customizable system monitor overlay for Windows, built with Python/PySide6. It features movable and groupable widgets, custom layouts, themes, historical data graphs, and full sensor support via LibreHardwareMonitor.

=========================
 Hanluku-system-monitor
=========================

A highly customizable system monitor overlay for Windows. Features movable widgets, custom layouts, themes, historical graphs, and full sensor support via LibreHardwareMonitor. Built with Python/PySide6.

<img width="491" height="407" alt="testing" src="https://github.com/user-attachments/assets/30c8d946-c591-47b1-bbce-89031daf36a8" />


--- Features & Usage ---

Layout Management:
With the layout function, you can save and load the arrangement, size, and settings of your widgets.
  - Create New Layout: Saves the current arrangement of all widgets and their settings under a new name.
  - Load Layout: Loads a previously saved layout and restores all widgets and settings.
  - Manage Layouts: Allows you to delete layouts that are no longer needed.
  - Reset Positions Only: Resets all widgets to the default stack without changing your color, font, or other settings.
  - Reset Everything: Completely resets the application to its factory state. All settings and layouts will be deleted.

Grouping Widgets:
You can group widgets together so they move and behave as a single unit.
  - Stack Group (Vertical): Drag a widget directly below another until it docks magnetically. Both widgets will then always have the same width and move together.
  - Horizontal Group: Drag a widget to the side of another.
  - Leave Group: Right-click on a widget in a group and select 'Leave Stack'.

Custom Sensors:
The application can only display a selection of the most important sensors directly. With Custom Sensors, you can add any sensor your hardware offers as its own widget.
  1. Open Configuration -> Sensor Diagnosis from the menu.
  2. Switch to the 'Sensor Explorer' tab. Here you will see all devices and sensors detected by the application.
  3. Expand the tree structure until you find the desired sensor (e.g., a case fan or a motherboard voltage).
  4. Right-click on the sensor and select 'Add as Custom Sensor'.
  5. Give it a descriptive name (e.g., 'Top Case Fan') and a unit (e.g., 'RPM') and save.
  6. The new sensor will now appear in the main menu under 'Custom Sensors' and can be displayed as a widget.

Monitoring & History:
The application can record sensor data over a longer period to analyze trends.
  - Opening the Window: Open the window via the menu 'Configuration -> Monitoring History...'.
  - Controlling Recording: Check the 'Enable data recording' checkbox to start collecting data. You can configure the interval, maximum storage duration, and file size.
  - Viewing & Exporting Data: Select one or more sensors from the list to view their history in the graph. You can save the collected data as a CSV file using the 'Export Data' button.

Tray Icon:
The icon in the system tray can be customized.
  - Shape & Color: You can change the shape and the default color of the icon.
  - Text: You can display a short text (e.g., 'CPU') in the icon and adjust its font size.
  - Blink on Alarm: If this option is enabled, the icon will switch to the alarm color when a threshold you have defined (see 'Alarm Values') is exceeded. You can set the blink rate (interval) and the duration of the blink.

Detailed Configuration:
In the 'Configuration' menu, you will find many more customization options:
  - Hardware Selection: If you have multiple graphics cards, hard drives, or network adapters, you can select which one to display here.
  - Display Settings: Change fonts, label texts, bar graph appearance, and the inner padding of the widgets.
  - Import & Export: Back up all your settings to a file or load a configuration from someone else.
  - Diagnostic Tools: 'Sensor Diagnosis' helps with hardware detection issues. 'System Health' provides information about the performance of the application itself.

General Window Controls:
  - Always on Top: Keeps the widgets above all other windows.
  - Lock Position: Locks the widgets in their current position to prevent accidental moving.
  - Alarm Values: Here you define the thresholds at which a sensor is considered to be in an 'alarm state' (e.g., CPU temperature > 90°C).
  - Color Management: Customize the color for each individual sensor in its normal and alarm state.

--------------------------------------------------

--- Third-Party Libraries ---

  - This project uses LibreHardwareMonitorLib.dll from the Libre Hardware Monitor project.
    Source: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
    License: Mozilla Public License 2.0.

  - Additionally, HidSharp.dll is used. This is a dependency of LibreHardwareMonitor required for communicating with certain USB devices.
    Source: https://github.com/a-j-m/HidSharp
    License: Apache License 2.0.

  - The application uses the Fira Code font.
    Source: https://github.com/tonsky/FiraCode
    License: SIL Open Font License 1.1.


--- License ---

This project is licensed under the Mozilla Public License 2.0.


--- Notes ---

"When the font is switched for Retina displays, or when many widgets are frequently updated, memory usage increases to 250 MB. To reduce alerts from the Performance Manager, reset the baseline in Configuration ► Performance Settings... or deactivate it."
