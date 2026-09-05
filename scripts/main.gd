extends Control

signal operator_signal(action: String)

const Chapter01 = preload("res://missions/chapter_01.gd")

@onready var chapter_label: Label = %ChapterLabel
@onready var mission_title: Label = %MissionTitle
@onready var briefing: Label = %Briefing
@onready var station_row: HBoxContainer = %StationRow
@onready var log_text: RichTextLabel = %LogText
@onready var action_row: HBoxContainer = %ActionRow
@onready var scan_controller: Node = %ScanController
@onready var mission_controller: Node = %MissionController
@onready var scan_toggle: CheckButton = %ScanToggle
@onready var scan_speed: HSlider = %ScanSpeed
@onready var text_size: OptionButton = %TextSize
@onready var reduced_motion: CheckButton = %ReducedMotion
@onready var sound_toggle: CheckButton = %SoundToggle

var station_scene := preload("res://scenes/station_panel.tscn")
var current_scene_index := 0
var active_buttons: Array[Button] = []

func _ready() -> void:
    _apply_console_theme()
    mission_controller.configure(Chapter01.missions())
    scan_toggle.toggled.connect(_on_scan_toggled)
    scan_speed.value_changed.connect(_on_scan_speed_changed)
    text_size.item_selected.connect(_on_text_size_selected)
    _render_mission()

func activate_switch_for_test() -> void:
    if scan_controller.enabled:
        scan_controller.activate_current()
        return
    var focused := get_viewport().gui_get_focus_owner() as Button
    if focused != null and action_row.is_ancestor_of(focused) and not focused.disabled:
        focused.pressed.emit()
    elif not active_buttons.is_empty() and not active_buttons[0].disabled:
        active_buttons[0].pressed.emit()

func _input(event: InputEvent) -> void:
    var switch_pressed := false
    if event is InputEventKey and event.pressed and not event.echo:
        switch_pressed = event.keycode == KEY_SPACE or event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER
    elif event is InputEventScreenTouch and event.pressed:
        switch_pressed = true
    if switch_pressed:
        get_viewport().set_input_as_handled()
        activate_switch_for_test()

func _render_mission() -> void:
    current_scene_index = mission_controller.current_index
    var mission: Dictionary = mission_controller.current_mission()
    chapter_label.text = "ASTERION / SIGNAL OPERATIONS / CHAPTER 01"
    mission_title.text = "%s  %s" % [mission.number, mission.title]
    briefing.text = mission.briefing
    _set_stations(mission.stations)
    log_text.text = mission.log
    _set_actions(mission.actions)

func _set_stations(states: Array) -> void:
    for child in station_row.get_children():
        station_row.remove_child(child)
        child.queue_free()
    for state in states:
        var panel := station_scene.instantiate()
        panel.station_name = state[0]
        station_row.add_child(panel)
        panel.set_station(state[0], state[1], state[2])

func _set_actions(actions: Array) -> void:
    for child in action_row.get_children():
        action_row.remove_child(child)
        child.queue_free()
    active_buttons.clear()
    for definition in actions:
        var button := Button.new()
        button.text = definition[0]
        button.set_meta("action", definition[1])
        button.custom_minimum_size = Vector2(260, 76)
        button.focus_mode = Control.FOCUS_ALL
        button.pressed.connect(func() -> void: _on_operator_action(definition[1]))
        action_row.add_child(button)
        active_buttons.append(button)
    scan_controller.configure(active_buttons)
    if not active_buttons.is_empty():
        active_buttons[0].grab_focus()

func _on_operator_action(action: String) -> void:
    operator_signal.emit(action)
    mission_controller.record_operator_signal(action)
    match current_scene_index:
        0: _handle_scene_one(action)
        1: _handle_scene_two(action)
        2: _handle_scene_three(action)
        3: _handle_scene_four(action)
        4: _handle_scene_five(action)

func _handle_scene_one(action: String) -> void:
    if action == "report_ready":
        _station(3).set_station("SIGNAL OPS", "READY", true)
        briefing.text = "Station report accepted. Signal Operations is in the readiness chain."
        log_text.text += "\n\n[color=#45d6a1]SIGNAL OPERATIONS: Station ready.[/color]\nCOMMAND: Readiness acknowledged. Hold for sequence assignment."
        _set_actions([["ACCEPT ASSIGNMENT", "continue"]])
    elif action == "continue":
        _advance_mission()

func _handle_scene_two(action: String) -> void:
    if action == "continue":
        mission_controller.advance_step()
        match mission_controller.step:
            1:
                _station(0).set_station("ENGINEERING", "READY", true)
                log_text.text += "\n\nENGINEERING: Capacitor alignment complete."
                _set_actions([["OBSERVE NAVIGATION", "continue"]])
            2:
                _station(1).set_station("NAVIGATION", "READY", true)
                log_text.text += "\nNAVIGATION: Corridor confirmed."
                _set_actions([["AWAIT COMMAND", "continue"]])
            3:
                _station(2).set_station("COMMAND", "AUTHORIZED", true)
                log_text.text += "\nCOMMAND: Signal Operations, initiate transition."
                _set_actions([["ACTUATE", "actuate"]])
            4:
                _advance_mission()
    elif action == "actuate":
        log_text.text += "\n\n[color=#45d6a1]Signal received. Transition underway.[/color]"
        briefing.text = "The signal completed a sequence whose prerequisites were already established."
        _set_actions([["CONTINUE", "continue"]])
        mission_controller.step = 3

func _handle_scene_three(action: String) -> void:
    if action == "actuate" and not mission_controller.has_flag("corrected"):
        log_text.text += "\n\n[color=#e2b86b]Transition inhibited.\nNavigation corridor was not confirmed.\nEngineering returns drive charge to standby.[/color]\n\n[color=#6f8499]TRACE THE SIGNAL[/color]\nWhat did we expect? A valid transition.\nWhat actually happened? The transition was inhibited.\nWhere did they diverge? Navigation corridor confirmation.\nWhat assumption was false? That all dependencies were ready.\nCorrection: confirm the corridor, then run the sequence again."
        _station(0).set_station("ENGINEERING", "STANDBY", false)
        _set_actions([["RUN SEQUENCE AGAIN", "retry"]])
    elif action == "retry":
        mission_controller.set_flag("corrected")
        _station(0).set_station("ENGINEERING", "CHARGING", false)
        log_text.text += "\n\nENGINEERING: Restoring drive charge.\nNAVIGATION: Corridor verification complete."
        _station(1).set_station("NAVIGATION", "READY", true)
        _set_actions([["CONFIRM READY STATE", "continue"]])
    elif action == "continue" and mission_controller.has_flag("corrected"):
        _station(0).set_station("ENGINEERING", "READY", true)
        log_text.text += "\nENGINEERING: Drive charge restored. All dependencies report ready."
        _set_actions([["ACTUATE", "actuate"]])
    elif action == "actuate" and mission_controller.has_flag("corrected"):
        log_text.text += "\n\n[color=#45d6a1]Signal received. Sequence completed.[/color]"
        _set_actions([["CONTINUE", "next_scene"]])
    elif action == "next_scene":
        _advance_mission()

func _handle_scene_four(action: String) -> void:
    if action == "actuate" and not mission_controller.has_flag("held"):
        log_text.text += "\n\n[color=#e2b86b]Transition inhibited. Protective condition remains latched.[/color]\nThe primary reports were valid; the full ready state was not. Re-evaluate the complete station."
        _set_actions([["HOLD SIGNAL", "hold"]])
    elif action == "hold":
        mission_controller.set_flag("held")
        log_text.text += "\n\n[color=#45d6a1]SIGNAL OPERATIONS: Holding signal.[/color]\nENGINEERING: Hold acknowledged. Thermal recovery remains in progress."
        _set_actions([["MONITOR INTERLOCK", "continue"]])
    elif action == "continue" and mission_controller.has_flag("held") and not mission_controller.has_flag("clear"):
        mission_controller.set_flag("clear")
        _station(3).set_station("THERMAL", "CLEAR", true)
        log_text.text += "\n\nENGINEERING: Thermal interlock CLEAR.\nCOMMAND: Signal Operations, re-evaluate transition state."
        _set_actions([["ACTUATE", "actuate"]])
    elif action == "actuate" and mission_controller.has_flag("clear"):
        log_text.text += "\n\n[color=#45d6a1]Signal received. Transition underway. Judgment confirmed by system state.[/color]"
        briefing.text = "Mastery is not blind obedience. Authority and readiness must still agree."
        _set_actions([["REVIEW PROCEDURE", "continue"]])
        mission_controller.set_flag("complete")
    elif action == "continue" and mission_controller.has_flag("complete"):
        _advance_mission()

func _handle_scene_five(action: String) -> void:
    if action == "complete":
        log_text.text += "\n\n[color=#d7e2ed]CHAPTER STATUS: Procedure understood. Station left ready.[/color]"
        briefing.text = "A single signal can carry enormous meaning when the operator understands the system around it."
        for button in active_buttons:
            button.disabled = true

func _advance_mission() -> void:
    if mission_controller.advance_mission():
        _render_mission()

func _station(index: int) -> Node:
    return station_row.get_child(index)

func _on_scan_toggled(value: bool) -> void:
    scan_controller.set_enabled(value)
    if not value and not active_buttons.is_empty():
        active_buttons[0].grab_focus()

func _on_scan_speed_changed(value: float) -> void:
    scan_controller.set_interval(value)

func _on_text_size_selected(index: int) -> void:
    var scale := [1.0, 1.2, 1.4][index] as float
    theme.default_font_size = roundi(18 * scale)
    chapter_label.add_theme_font_size_override("font_size", roundi(15 * scale))
    mission_title.add_theme_font_size_override("font_size", roundi(25 * scale))
    briefing.add_theme_font_size_override("font_size", roundi(17 * scale))
    for panel in station_row.get_children():
        panel.get_node("Layout/Text/StationName").add_theme_font_size_override("font_size", roundi(15 * scale))
        panel.get_node("Layout/Text/StationStatus").add_theme_font_size_override("font_size", roundi(18 * scale))

func _apply_console_theme() -> void:
    var console_theme := Theme.new()
    console_theme.default_font_size = 18
    console_theme.set_color("font_color", "Label", Color("d7e2ed"))
    console_theme.set_color("font_color", "Button", Color("eaf3fa"))
    console_theme.set_color("font_hover_color", "Button", Color.WHITE)
    console_theme.set_color("font_focus_color", "Button", Color.WHITE)
    console_theme.set_stylebox("normal", "Button", _panel_style("172536", "36516b", 2, 8))
    console_theme.set_stylebox("hover", "Button", _panel_style("20364a", "62b9df", 2, 8))
    console_theme.set_stylebox("focus", "Button", _panel_style("24445a", "75d8ff", 4, 8))
    console_theme.set_stylebox("pressed", "Button", _panel_style("24445a", "75d8ff", 4, 8))
    theme = console_theme

func _panel_style(fill: String, border: String, width: int, radius: int) -> StyleBoxFlat:
    var style := StyleBoxFlat.new()
    style.bg_color = Color(fill)
    style.border_color = Color(border)
    style.set_border_width_all(width)
    style.set_corner_radius_all(radius)
    style.content_margin_left = 18
    style.content_margin_right = 18
    style.content_margin_top = 12
    style.content_margin_bottom = 12
    return style
