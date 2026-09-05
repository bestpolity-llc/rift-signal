extends Node

signal scan_focus_changed(index: int)
signal scan_activated(index: int)

@export_range(0.8, 5.0, 0.1) var interval_seconds := 2.0
var enabled := false
var _targets: Array[Button] = []
var _index := -1
var _timer: Timer

func _ready() -> void:
    _timer = Timer.new()
    _timer.one_shot = false
    _timer.timeout.connect(_advance)
    add_child(_timer)

func configure(targets: Array[Button]) -> void:
    _targets = targets.filter(func(target: Button) -> bool: return is_instance_valid(target) and target.visible and not target.disabled)
    _index = -1
    if enabled:
        _restart()

func set_enabled(value: bool) -> void:
    enabled = value
    if not is_node_ready():
        return
    if enabled:
        _restart()
    else:
        _timer.stop()
        _index = -1

func set_interval(value: float) -> void:
    interval_seconds = clampf(value, 0.8, 5.0)
    if is_node_ready() and enabled:
        _timer.start(interval_seconds)

func activate_current() -> bool:
    if not enabled or _targets.is_empty():
        return false
    if _index < 0:
        _advance()
    var target := _targets[_index]
    if is_instance_valid(target) and not target.disabled:
        target.pressed.emit()
        scan_activated.emit(_index)
        return true
    return false

func _restart() -> void:
    _timer.stop()
    _index = -1
    _advance()
    _timer.start(interval_seconds)

func _advance() -> void:
    if _targets.is_empty():
        return
    _index = (_index + 1) % _targets.size()
    _targets[_index].grab_focus()
    scan_focus_changed.emit(_index)
