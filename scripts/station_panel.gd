extends PanelContainer

signal station_state_changed(station_name: String, status: String, ready: bool)
signal station_ready(station_name: String)

@onready var name_label: Label = %StationName
@onready var status_label: Label = %StationStatus
@onready var indicator: ColorRect = %Indicator

var station_name := "STATION"
var is_ready := false

func _ready() -> void:
    set_station(station_name, "STANDBY", false)

func set_station(new_name: String, status: String, ready: bool) -> void:
    station_name = new_name
    is_ready = ready
    if is_node_ready():
        name_label.text = station_name.to_upper()
        status_label.text = status.to_upper()
        status_label.modulate = Color("8fe3c1") if ready else Color("9aa9ba")
        indicator.color = Color("45d6a1") if ready else Color("526579")
    station_state_changed.emit(station_name, status, ready)
    if ready:
        station_ready.emit(station_name)
