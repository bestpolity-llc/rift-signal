extends Control

signal operator_signal(action: String)

@onready var chapter_label: Label = %ChapterLabel
@onready var mission_title: Label = %MissionTitle
@onready var briefing: Label = %Briefing
@onready var station_row: HBoxContainer = %StationRow
@onready var log_text: RichTextLabel = %LogText
@onready var action_row: HBoxContainer = %ActionRow
@onready var scan_controller: Node = %ScanController
@onready var scan_toggle: CheckButton = %ScanToggle
@onready var scan_speed: HSlider = %ScanSpeed
@onready var text_size: OptionButton = %TextSize
@onready var reduced_motion: CheckButton = %ReducedMotion
@onready var sound_toggle: CheckButton = %SoundToggle

var station_scene := preload("res://scenes/station_panel.tscn")
var report_button: Button
var scene_complete := false

func _ready() -> void:
    _apply_console_theme()
    _build_scene_one()
    scan_toggle.toggled.connect(_on_scan_toggled)
    scan_speed.value_changed.connect(_on_scan_speed_changed)
    text_size.item_selected.connect(_on_text_size_selected)
    report_button.grab_focus()

func activate_switch_for_test() -> void:
    if scan_controller.enabled:
        scan_controller.activate_current()
    else:
        var focused := get_viewport().gui_get_focus_owner() as Button
        if focused != null and action_row.is_ancestor_of(focused):
            focused.pressed.emit()
        elif report_button != null and report_button.visible and not report_button.disabled:
            report_button.pressed.emit()

func _input(event: InputEvent) -> void:
    var switch_pressed := false
    if event is InputEventKey and event.pressed and not event.echo:
        switch_pressed = event.keycode == KEY_SPACE or event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER
    elif event is InputEventScreenTouch and event.pressed:
        switch_pressed = true
    if not switch_pressed:
        return
    get_viewport().set_input_as_handled()
    activate_switch_for_test()

func _build_scene_one() -> void:
    chapter_label.text = "ASTERION / SIGNAL OPERATIONS / CHAPTER 01"
    mission_title.text = "01  REPORT TO SIGNAL OPERATIONS"
    briefing.text = "You are the Signal Operations Specialist aboard Asterion. Your station completes sequences that no other station can complete alone."
    _set_stations([
        ["ENGINEERING", "CAPABILITY", false],
        ["NAVIGATION", "PATH", false],
        ["COMMAND", "AUTHORITY", false],
        ["SIGNAL OPS", "AWAITING REPORT", false],
    ])
    log_text.text = "[color=#6f8499]OPERATIONS BRIEF[/color]\n\nEngineering supplies capability.\nNavigation supplies the path.\nCommand supplies authority.\nSignal Operations completes certain sequences.\n\n[color=#d7e2ed]Report when your station is ready.[/color]"
    report_button = _make_action("REPORT READY", "report_ready")
    var scan_targets: Array[Button] = [report_button]
    scan_controller.configure(scan_targets)

func _set_stations(states: Array) -> void:
    for child in station_row.get_children():
        child.queue_free()
    for state in states:
        var panel := station_scene.instantiate()
        panel.station_name = state[0]
        station_row.add_child(panel)
        panel.set_station(state[0], state[1], state[2])

func _make_action(label: String, action: String) -> Button:
    var button := Button.new()
    button.text = label
    button.custom_minimum_size = Vector2(260, 76)
    button.focus_mode = Control.FOCUS_ALL
    button.pressed.connect(func() -> void: _on_operator_action(action))
    action_row.add_child(button)
    return button

func _on_operator_action(action: String) -> void:
    operator_signal.emit(action)
    if action == "report_ready" and not scene_complete:
        scene_complete = true
        report_button.disabled = true
        log_text.text += "\n\n[color=#45d6a1]SIGNAL OPERATIONS: Station ready.[/color]\nCOMMAND: Readiness acknowledged. Hold for sequence assignment."
        briefing.text = "Station report accepted. Signal Operations is in the readiness chain."
        var signal_panel := station_row.get_child(3)
        signal_panel.set_station("SIGNAL OPS", "READY", true)

func _on_scan_toggled(value: bool) -> void:
    scan_controller.set_enabled(value)
    if not value and report_button != null:
        report_button.grab_focus()

func _on_scan_speed_changed(value: float) -> void:
    scan_controller.set_interval(value)

func _on_text_size_selected(index: int) -> void:
    var sizes := [16, 20, 24]
    theme.default_font_size = sizes[index]

func _apply_console_theme() -> void:
    var console_theme := Theme.new()
    console_theme.default_font_size = 18
    console_theme.set_color("font_color", "Label", Color("d7e2ed"))
    console_theme.set_color("font_color", "Button", Color("eaf3fa"))
    console_theme.set_color("font_hover_color", "Button", Color.WHITE)
    console_theme.set_color("font_focus_color", "Button", Color.WHITE)
    var button_normal := _panel_style("172536", "36516b", 2, 8)
    var button_hover := _panel_style("20364a", "62b9df", 2, 8)
    var button_focus := _panel_style("24445a", "75d8ff", 4, 8)
    console_theme.set_stylebox("normal", "Button", button_normal)
    console_theme.set_stylebox("hover", "Button", button_hover)
    console_theme.set_stylebox("focus", "Button", button_focus)
    console_theme.set_stylebox("pressed", "Button", button_focus)
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
