extends RefCounted

static func missions() -> Array[Dictionary]:
    return [
        {
            "number": "01",
            "title": "REPORT TO SIGNAL OPERATIONS",
            "briefing": "You are the Signal Operations Specialist aboard Asterion. Your station completes sequences that no other station can complete alone.",
            "stations": [
                ["ENGINEERING", "CAPABILITY", false], ["NAVIGATION", "PATH", false],
                ["COMMAND", "AUTHORITY", false], ["SIGNAL OPS", "AWAITING REPORT", false]
            ],
            "log": "[color=#6f8499]OPERATIONS BRIEF[/color]\n\nEngineering supplies capability.\nNavigation supplies the path.\nCommand supplies authority.\nSignal Operations completes certain sequences.\n\n[color=#d7e2ed]Report when your station is ready.[/color]",
            "actions": [["REPORT READY", "report_ready"]]
        },
        {
            "number": "02", "title": "FIRST ACTUATION",
            "briefing": "Observe the readiness chain. Signal only when capability, path, and authority align.",
            "stations": [["ENGINEERING", "ALIGNING", false], ["NAVIGATION", "VERIFYING", false], ["COMMAND", "STANDBY", false], ["SIGNAL OPS", "READY", true]],
            "log": "[color=#6f8499]SEQUENCE ASSIGNMENT[/color]\n\nEngineering is aligning the transition capacitor. Observe the station reports.",
            "actions": [["OBSERVE ENGINEERING", "continue"]]
        },
        {
            "number": "03", "title": "PREMATURE SIGNAL",
            "briefing": "A signal is information. If a sequence fails, trace where expectation and state diverged.",
            "stations": [["ENGINEERING", "READY", true], ["NAVIGATION", "VERIFYING", false], ["COMMAND", "AUTHORIZED", true], ["SIGNAL OPS", "READY", true]],
            "log": "[color=#6f8499]SEQUENCE STATUS[/color]\n\nENGINEERING: Drive charge available.\nCOMMAND: Transition authorized.\nNAVIGATION: Corridor verification in progress.",
            "actions": [["ACTUATE", "actuate"]]
        },
        {
            "number": "04", "title": "THE FIRST REAL JUDGMENT",
            "briefing": "Primary reports are ready. Protective conditions remain part of the system state.",
            "stations": [["ENGINEERING", "READY", true], ["NAVIGATION", "READY", true], ["COMMAND", "AUTHORIZED", true], ["THERMAL", "RECOVERY LATCHED", false]],
            "log": "[color=#6f8499]TRANSITION WINDOW[/color]\n\nENGINEERING: READY\nNAVIGATION: READY\nCOMMAND: AUTHORIZED\n\n[color=#e2b86b]THERMAL INTERLOCK: RECOVERY LATCHED[/color]\n\nCommand authority does not remove operator judgment.",
            "actions": [["ACTUATE", "actuate"], ["HOLD SIGNAL", "hold"]]
        },
        {
            "number": "05", "title": "PROCEDURE",
            "briefing": "The sequence can be stated as procedure, then expressed as code.",
            "stations": [["ENGINEERING", "CONDITION", true], ["NAVIGATION", "CONDITION", true], ["COMMAND", "CONDITION", true], ["PROTECTIVE", "CONDITION", true]],
            "log": "[color=#6f8499]PROCEDURE ANALYSIS[/color]\n\nWHEN Engineering is ready\nAND Navigation is ready\nAND Command is authorized\nAND protective conditions are clear\nTHEN actuate\n\n[color=#75d8ff]if (\n    engineering.ready\n    and navigation.ready\n    and command.authorized\n    and protective_conditions.clear\n):\n    initiate_transition()[/color]\n\n[color=#45d6a1]The syntax is new. The thought is not.[/color]\n\nYou have already used conditions, state, conjunction, sequence, inhibition, retry, debugging, and procedure.",
            "actions": [["CHAPTER COMPLETE", "complete"]]
        }
    ]
